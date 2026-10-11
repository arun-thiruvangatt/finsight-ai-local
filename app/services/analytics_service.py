"""All aggregation happens in SQL; Python only shapes and fills gaps."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, literal, select
from sqlalchemy.orm import aliased
from sqlmodel import Session

from app.core.exceptions import AppError, NotFoundError
from app.db.models import Category, Transaction
from app.services import category_service
from app.utils.dates import add_months, month_bounds, month_str, parse_month
from app.utils.money import ZERO, D, pct_change, percentage, quantize

EXPENSE, INCOME = "EXPENSE", "INCOME"  # TRANSFER rows never count as income/expense


def _where(user_id: int, start: date, end: date, ttype: str, category_ids: list[int] | None = None) -> list:
    w = [Transaction.user_id == user_id, Transaction.transaction_date >= start,
         Transaction.transaction_date < end, Transaction.transaction_type == ttype]
    if category_ids is not None:
        w.append(Transaction.category_id.in_(category_ids))
    return w


def sum_amount(session: Session, user_id: int, ttype: str, start: date, end: date,
               category_ids: list[int] | None = None) -> Decimal:
    q = select(func.coalesce(func.sum(Transaction.amount), 0)).where(*_where(user_id, start, end, ttype, category_ids))
    return quantize(session.execute(q).scalar_one())


def months_back(end_month: str, n: int) -> list[str]:
    """n months ascending, ending at end_month inclusive."""
    end = parse_month(end_month)
    return [month_str(add_months(end, -i)) for i in range(n - 1, -1, -1)]


def get_monthly_summary(session: Session, user_id: int, month: str) -> dict:
    start, end = month_bounds(month)
    income = sum_amount(session, user_id, INCOME, start, end)
    expenses = sum_amount(session, user_id, EXPENSE, start, end)
    savings = income - expenses
    return {"month": month, "income": income, "expenses": expenses, "savings": savings,
            "savings_rate": percentage(savings, income) if income > 0 else ZERO}


def _summary(session: Session, user_id: int, ttype: str, start: date, end: date) -> dict:
    row = session.execute(select(func.coalesce(func.sum(Transaction.amount), 0), func.count(Transaction.id))
                          .where(*_where(user_id, start, end, ttype))).one()
    total, count = quantize(row[0]), int(row[1])
    return {"from": start, "to": end, "total": total, "transaction_count": count,
            "average_transaction": quantize(total / count) if count else ZERO}


def get_expense_summary(session: Session, user_id: int, start: date, end: date) -> dict:
    return _summary(session, user_id, EXPENSE, start, end)


def get_income_summary(session: Session, user_id: int, start: date, end: date) -> dict:
    out = _summary(session, user_id, INCOME, start, end)
    out["by_category"] = get_category_breakdown(session, user_id, start, end, ttype=INCOME)
    return out


def get_category_breakdown(session: Session, user_id: int, start: date, end: date, ttype: str = EXPENSE,
                           level: str = "top") -> list[dict]:
    """level='top' rolls sub-categories up into their parent; 'leaf' keeps them separate."""
    c, p = aliased(Category), aliased(Category)
    if level == "top":
        cid, name = func.coalesce(p.id, c.id), func.coalesce(p.name, c.name, literal("Uncategorized"))
    else:
        cid, name = c.id, func.coalesce(c.name, literal("Uncategorized"))
    q = (select(cid.label("cid"), name.label("name"), func.sum(Transaction.amount), func.count(Transaction.id))
         .select_from(Transaction)
         .outerjoin(c, Transaction.category_id == c.id).outerjoin(p, c.parent_id == p.id)
         .where(*_where(user_id, start, end, ttype)).group_by(cid, name)
         .order_by(func.sum(Transaction.amount).desc()))
    rows = session.execute(q).all()
    total = sum((D(r[2]) for r in rows), ZERO)
    return [{"category_id": r[0], "category": r[1], "amount": quantize(r[2]),
             "percentage": percentage(r[2], total), "transaction_count": int(r[3])} for r in rows]


def get_category_expenses(session: Session, user_id: int, category_name: str, start: date, end: date) -> dict:
    cat = category_service.find_by_name(session, user_id, category_name)
    if cat is None:
        raise NotFoundError(f"No category matching '{category_name}'.", code="CATEGORY_NOT_FOUND")
    ids = category_service.descendant_ids(session, user_id, cat.id)
    q = (select(Category.name, func.sum(Transaction.amount), func.count(Transaction.id))
         .join(Category, Transaction.category_id == Category.id)
         .where(*_where(user_id, start, end, EXPENSE, ids)).group_by(Category.name)
         .order_by(func.sum(Transaction.amount).desc()))
    subs = [{"category": r[0], "amount": quantize(r[1]), "transaction_count": int(r[2])}
            for r in session.execute(q).all()]
    return {"category": cat.name, "from": start, "to": end,
            "amount": sum((s["amount"] for s in subs), ZERO),
            "transaction_count": sum(s["transaction_count"] for s in subs), "subcategories": subs}


def _monthly_totals(session: Session, user_id: int, months: list[str],
                    category_ids: list[int] | None = None) -> dict[tuple[str, str], Decimal]:
    start, _ = month_bounds(months[0])
    _, end = month_bounds(months[-1])
    bucket = func.to_char(Transaction.transaction_date, "YYYY-MM")
    q = (select(bucket, Transaction.transaction_type, func.sum(Transaction.amount))
         .where(Transaction.user_id == user_id, Transaction.transaction_date >= start,
                Transaction.transaction_date < end, Transaction.transaction_type.in_([INCOME, EXPENSE]))
         .group_by(bucket, Transaction.transaction_type))
    if category_ids is not None:
        q = q.where(Transaction.category_id.in_(category_ids))
    return {(r[0], r[1]): quantize(r[2]) for r in session.execute(q).all()}


def get_cashflow(session: Session, user_id: int, months: int, end_month: str) -> list[dict]:
    if not 1 <= months <= 36:
        raise AppError("months must be between 1 and 36.", code="INVALID_RANGE")
    ms = months_back(end_month, months)
    totals = _monthly_totals(session, user_id, ms)
    out = []
    for m in ms:
        inc, exp = totals.get((m, INCOME), ZERO), totals.get((m, EXPENSE), ZERO)
        out.append({"month": m, "income": inc, "expenses": exp, "net": inc - exp})
    return out


def get_monthly_trends(session: Session, user_id: int, months: int, end_month: str,
                       category_name: str | None = None) -> list[dict]:
    if not 1 <= months <= 36:
        raise AppError("months must be between 1 and 36.", code="INVALID_RANGE")
    ids = None
    if category_name:
        cat = category_service.find_by_name(session, user_id, category_name)
        if cat is None:
            raise NotFoundError(f"No category matching '{category_name}'.", code="CATEGORY_NOT_FOUND")
        ids = category_service.descendant_ids(session, user_id, cat.id)
    ms = months_back(end_month, months)
    totals = _monthly_totals(session, user_id, ms, ids)
    return [{"month": m, "expenses": totals.get((m, EXPENSE), ZERO), "income": totals.get((m, INCOME), ZERO)}
            for m in ms]


def compare_months(session: Session, user_id: int, previous: str, current: str) -> dict:
    a, b = get_monthly_summary(session, user_id, previous), get_monthly_summary(session, user_id, current)
    (a0, a1), (b0, b1) = month_bounds(previous), month_bounds(current)
    ca = {r["category"]: r["amount"] for r in get_category_breakdown(session, user_id, a0, a1)}
    cb = {r["category"]: r["amount"] for r in get_category_breakdown(session, user_id, b0, b1)}
    diffs = []
    for name in set(ca) | set(cb):
        prev, cur = ca.get(name, ZERO), cb.get(name, ZERO)
        diffs.append({"category": name, "previous": prev, "current": cur, "difference": cur - prev,
                      "percentage_change": pct_change(prev, cur)})
    diffs.sort(key=lambda d: d["difference"], reverse=True)
    return {
        "previous_month": {"month": previous, "income": a["income"], "expenses": a["expenses"]},
        "current_month": {"month": current, "income": b["income"], "expenses": b["expenses"]},
        "difference": b["expenses"] - a["expenses"],
        "percentage_change": pct_change(a["expenses"], b["expenses"]),
        "top_increases": [d for d in diffs if d["difference"] > 0][:5],
        "top_decreases": [d for d in reversed(diffs) if d["difference"] < 0][:5],
    }


def get_top_merchants(session: Session, user_id: int, start: date, end: date, limit: int = 10) -> list[dict]:
    m = func.coalesce(Transaction.merchant, literal("Unknown"))
    q = (select(m, func.sum(Transaction.amount), func.count(Transaction.id))
         .where(*_where(user_id, start, end, EXPENSE)).group_by(m)
         .order_by(func.sum(Transaction.amount).desc()).limit(limit))
    return [{"merchant": r[0], "amount": quantize(r[1]), "transaction_count": int(r[2])}
            for r in session.execute(q).all()]


def get_daily_spending(session: Session, user_id: int, start: date, end: date) -> list[dict]:
    q = (select(Transaction.transaction_date, func.sum(Transaction.amount))
         .where(*_where(user_id, start, end, EXPENSE)).group_by(Transaction.transaction_date)
         .order_by(Transaction.transaction_date))
    return [{"date": r[0], "amount": quantize(r[1])} for r in session.execute(q).all()]


def total_balance(session: Session, user_id: int) -> Decimal:
    from app.db.models import Account
    q = select(func.coalesce(func.sum(Account.current_balance), 0)).where(
        Account.user_id == user_id, Account.is_active == True)  # noqa: E712
    return quantize(session.execute(q).scalar_one())
