"""Recurring expense detection from interval + amount regularity."""
import calendar
import statistics
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlmodel import Session

from app.core.constants import Frequency
from app.db.models import RecurringTransaction, Transaction
from app.utils.dates import add_months
from app.utils.money import quantize

MIN_CONFIDENCE = 0.6
LOOKBACK_DAYS = 400


def classify_interval(median_days: float) -> Frequency | None:
    if 5 <= median_days <= 9:
        return Frequency.WEEKLY
    if 26 <= median_days <= 35:
        return Frequency.MONTHLY
    if 350 <= median_days <= 380:
        return Frequency.YEARLY
    return None


def _next_date(last: date, freq: Frequency, median: float) -> date:
    if freq == Frequency.MONTHLY:
        nxt = add_months(last.replace(day=1), 1)
        return nxt.replace(day=min(last.day, calendar.monthrange(nxt.year, nxt.month)[1]))
    if freq == Frequency.YEARLY:
        nxt = add_months(last.replace(day=1), 12)
        return nxt.replace(day=min(last.day, calendar.monthrange(nxt.year, nxt.month)[1]))
    return last + timedelta(days=round(median))


def analyze_series(dates: list[date], amounts: list[Decimal]) -> dict | None:
    """Pure function. Returns pattern dict or None when the series is not regular enough."""
    pairs = sorted(zip(dates, amounts, strict=True))
    ds, am = [p[0] for p in pairs], [p[1] for p in pairs]
    n = len(ds)
    if n < 2:
        return None
    intervals = [(ds[i] - ds[i - 1]).days for i in range(1, n)]
    intervals = [i for i in intervals if i > 0]
    if not intervals:
        return None
    median = statistics.median(intervals)
    freq = classify_interval(median)
    if freq is None or (n < 3 and freq != Frequency.YEARLY):
        return None
    consistency = 1 - min(1.0, statistics.mean(abs(i - median) for i in intervals) / median)
    mean_amt = sum(am) / n
    cv = float(Decimal(str(statistics.pstdev([float(a) for a in am]))) / mean_amt) if mean_amt else 1.0
    confidence = round(0.5 * consistency + 0.35 * (1 - min(cv, 1.0)) + 0.15 * min(1.0, n / 6), 2)
    return {"frequency": freq.value, "confidence": confidence, "average_amount": quantize(mean_amt),
            "last_date": ds[-1], "next_expected": _next_date(ds[-1], freq, median),
            "interval_days": median, "occurrences": n}


def detect_recurring(session: Session, user_id: int, today: date | None = None) -> list[dict]:
    today = today or date.today()
    since = today - timedelta(days=LOOKBACK_DAYS)
    key = func.lower(func.trim(Transaction.merchant))
    candidates = [r[0] for r in session.execute(
        select(key).where(Transaction.user_id == user_id, Transaction.transaction_type == "EXPENSE",
                          Transaction.transaction_date >= since, Transaction.merchant.is_not(None))
        .group_by(key).having(func.count(Transaction.id) >= 2)).all()]

    detected: dict[str, tuple[str, dict]] = {}
    if candidates:
        rows = session.execute(
            select(key, Transaction.merchant, Transaction.transaction_date, Transaction.amount)
            .where(Transaction.user_id == user_id, Transaction.transaction_type == "EXPENSE",
                   Transaction.transaction_date >= since, key.in_(candidates))).all()
        grouped: dict[str, list] = {}
        for k, merchant, d, a in rows:
            grouped.setdefault(k, []).append((merchant, d, a))
        for k, items in grouped.items():
            pattern = analyze_series([i[1] for i in items], [i[2] for i in items])
            if pattern and pattern["confidence"] >= MIN_CONFIDENCE:
                display = Counter(i[0] for i in items).most_common(1)[0][0]
                detected[k] = (display, pattern)

    existing = {r.merchant.lower(): r for r in session.execute(
        select(RecurringTransaction).where(RecurringTransaction.user_id == user_id)).scalars()}
    for k, (display, p) in detected.items():
        grace = timedelta(days=round(p["interval_days"] * 0.5))
        active = p["next_expected"] + grace >= today
        rec = existing.pop(k, None) or RecurringTransaction(user_id=user_id, merchant=display, frequency=p["frequency"],
                                                            average_amount=p["average_amount"])
        rec.merchant, rec.frequency, rec.average_amount = display, p["frequency"], p["average_amount"]
        rec.next_expected_date, rec.last_transaction_date = p["next_expected"], p["last_date"]
        rec.confidence, rec.is_active = p["confidence"], active
        session.add(rec)
    for stale in existing.values():  # no longer matches a pattern
        stale.is_active = False
        session.add(stale)

    session.execute(update(Transaction).where(Transaction.user_id == user_id).values(is_recurring=False))
    if detected:
        session.execute(update(Transaction).where(
            Transaction.user_id == user_id, Transaction.transaction_type == "EXPENSE",
            key.in_(list(detected))).values(is_recurring=True))
    session.commit()
    return [{"merchant": d, **{k: v for k, v in p.items() if k != "interval_days"}} for d, p in detected.values()]


def list_recurring(session: Session, user_id: int, active_only: bool = True) -> list[dict]:
    q = select(RecurringTransaction).where(RecurringTransaction.user_id == user_id)
    if active_only:
        q = q.where(RecurringTransaction.is_active == True)  # noqa: E712
    rows = session.execute(q.order_by(RecurringTransaction.average_amount.desc())).scalars().all()
    return [{"merchant": r.merchant, "average_amount": r.average_amount, "frequency": r.frequency,
             "next_expected_date": r.next_expected_date, "last_transaction_date": r.last_transaction_date,
             "confidence": r.confidence} for r in rows]


def monthly_equivalent(average_amount: Decimal, frequency: str) -> Decimal:
    factor = {"weekly": Decimal("4.345"), "monthly": Decimal("1"), "yearly": Decimal("1") / 12}[frequency]
    return quantize(average_amount * factor)
