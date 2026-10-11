"""Deterministic insight generation. Text is templated from computed facts - no LLM involved,
so every number in an insight is traceable to the database."""
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlmodel import Session

from app.db.models import AIInsight
from app.services import analytics_service, anomaly_service, budget_service, goal_service, recurring_service
from app.utils.dates import add_months, month_str, previous_month
from app.utils.money import ZERO, format_inr

MIN_ABS_INCREASE = Decimal("500")
MIN_PCT_INCREASE = Decimal("20")


def _add(session: Session, user_id: int, existing: set[str], *, itype: str, key: str, title: str, description: str,
         severity: str = "INFO", data: dict | None = None, ttl_days: int = 45) -> bool:
    dedupe = f"{itype}:{key}"
    if dedupe in existing:
        return False
    existing.add(dedupe)
    from app.utils.serialization import to_jsonable
    session.add(AIInsight(user_id=user_id, insight_type=itype, title=title, description=description,
                          severity=severity, data=to_jsonable(data or {}), dedupe_key=dedupe,
                          expires_at=datetime.now(UTC) + timedelta(days=ttl_days)))
    return True


def generate_monthly_insights(session: Session, user_id: int, today: date | None = None) -> int:
    today = today or date.today()
    existing = set(session.execute(select(AIInsight.dedupe_key).where(AIInsight.user_id == user_id)).scalars())
    created = 0
    last = month_str(add_months(today.replace(day=1), -1))
    before = previous_month(last)

    summary = analytics_service.get_monthly_summary(session, user_id, last)
    if summary["income"] or summary["expenses"]:
        created += _add(session, user_id, existing, itype="MONTHLY_SUMMARY", key=last,
                        title=f"Summary for {last}", data=summary, ttl_days=90,
                        description=(f"In {last} you earned {format_inr(summary['income'])} and spent "
                                     f"{format_inr(summary['expenses'])}, saving {format_inr(summary['savings'])} "
                                     f"({summary['savings_rate']}% of income)."))
        cmp_ = analytics_service.compare_months(session, user_id, before, last)
        total_pct = cmp_["percentage_change"]
        if total_pct is not None and total_pct >= 10 and cmp_["difference"] >= MIN_ABS_INCREASE:
            top = cmp_["top_increases"][:2]
            extra = " Main contributors: " + ", ".join(
                f"{t['category']} (+{format_inr(t['difference'])})" for t in top) + "." if top else ""
            created += _add(session, user_id, existing, itype="SPENDING_INCREASE", key=last,
                            title="Spending went up", severity="WARNING", data=cmp_,
                            description=f"Your spending rose {total_pct}% ({format_inr(cmp_['difference'])}) in "
                                        f"{last} compared with {before}.{extra}")
        for row in cmp_["top_increases"]:
            pct = row["percentage_change"]
            if pct is not None and pct >= MIN_PCT_INCREASE and row["difference"] >= MIN_ABS_INCREASE:
                created += _add(session, user_id, existing, itype="CATEGORY_TREND", key=f"{last}:{row['category']}",
                                title=f"{row['category']} spending is up", severity="INFO", data=row,
                                description=f"{row['category']} spending increased by {pct}% "
                                            f"({format_inr(row['previous'])} -> {format_inr(row['current'])}) "
                                            f"between {before} and {last}.")
        if cmp_["top_increases"]:
            top = cmp_["top_increases"][0]
            saving = (top["current"] * Decimal("0.10")).quantize(Decimal("1"))
            if saving > 0 and top["difference"] >= MIN_ABS_INCREASE:
                created += _add(session, user_id, existing, itype="SAVING_OPPORTUNITY", key=f"{last}:{top['category']}",
                                title=f"Saving opportunity: {top['category']}", data=top,
                                description=f"Estimate: trimming {top['category']} by 10% would free up about "
                                            f"{format_inr(saving)} a month.")

    cur = month_str(today)
    for st in budget_service.all_statuses(session, user_id, today):
        if st["warnings"]:
            bucket = int(st["usage_percentage"] // 10 * 10)
            sev = "CRITICAL" if st["spent"] > st["budget"] else "WARNING"
            created += _add(session, user_id, existing, itype="BUDGET_WARNING", key=f"{st['budget_id']}:{cur}:{bucket}",
                            title=f"Budget alert: {st['name']}", severity=sev, data=st, ttl_days=35,
                            description=" ".join(st["warnings"]))

    recurring = recurring_service.list_recurring(session, user_id)
    if recurring:
        monthly = sum((recurring_service.monthly_equivalent(r["average_amount"], r["frequency"]) for r in recurring), ZERO)
        top = recurring[0]
        created += _add(session, user_id, existing, itype="RECURRING_EXPENSE", key=f"{cur}:{len(recurring)}",
                        title="Recurring expenses", data={"count": len(recurring), "monthly_total": monthly},
                        description=f"You have {len(recurring)} recurring expenses costing about "
                                    f"{format_inr(monthly)} per month. Largest: {top['merchant']} "
                                    f"({format_inr(top['average_amount'])}, {top['frequency']}).")

    for a in anomaly_service.list_anomalies(session, user_id, limit=3, days=30):
        created += _add(session, user_id, existing, itype="UNUSUAL_TRANSACTION", key=str(a["transaction_id"]),
                        title="Unusual transaction", severity="WARNING", data=a, description=a["reason"] or "")

    for g in goal_service.list_goals(session, user_id):
        if g.status != "ACTIVE":
            continue
        p = goal_service.progress(session, g, today)
        bucket = int(p["progress_percentage"] // 10 * 10)
        created += _add(session, user_id, existing, itype="GOAL_PROGRESS", key=f"{g.id}:{bucket}",
                        title=f"Goal progress: {g.name}", data=p,
                        description=f"'{g.name}' is {p['progress_percentage']}% complete "
                                    f"({format_inr(p['current_amount'])} of {format_inr(p['target_amount'])}). "
                                    + (f"Required contribution to hit the target date: "
                                       f"{format_inr(p['required_monthly_contribution'])}/month."
                                       if p["required_monthly_contribution"] is not None else ""))
    session.commit()
    return created


def list_insights(session: Session, user_id: int, limit: int = 50) -> list[AIInsight]:
    now = datetime.now(UTC)
    q = (select(AIInsight).where(AIInsight.user_id == user_id)
         .where((AIInsight.expires_at.is_(None)) | (AIInsight.expires_at > now))
         .order_by(AIInsight.generated_at.desc(), AIInsight.id.desc()).limit(limit))
    return list(session.execute(q).scalars())

