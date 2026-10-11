"""Statistical anomaly detection (z-score vs merchant / category baselines computed in SQL)."""
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlmodel import Session

from app.db.models import Transaction
from app.utils.money import D, format_inr

MIN_HISTORY = 5
Z_THRESHOLD = Decimal("3")
MIN_STD_RATIO = Decimal("0.10")  # std floor = 10% of mean, avoids flagging tiny wobbles on fixed bills
HISTORY_DAYS = 365


@dataclass
class Baseline:
    mean: Decimal
    std: Decimal
    n: int
    label: str


@dataclass
class AnomalyResult:
    score: float
    z: Decimal
    reason: str


def evaluate(amount: Decimal, baseline: Baseline) -> AnomalyResult | None:
    """Pure function: is `amount` unusual versus `baseline`?"""
    if baseline.n < MIN_HISTORY or baseline.mean <= 0:
        return None
    std = max(baseline.std, baseline.mean * MIN_STD_RATIO)
    z = (amount - baseline.mean) / std
    if z < Z_THRESHOLD:
        return None
    score = min(0.99, float(z / (z + 3)))
    reason = (f"Amount {format_inr(amount)} is significantly higher than your usual {baseline.label} "
              f"(average {format_inr(baseline.mean)}, {z:.1f} standard deviations above).")
    return AnomalyResult(round(score, 3), z, reason)


def _stats(session: Session, user_id: int, group_col, before: date) -> dict:
    q = (select(group_col, func.avg(Transaction.amount), func.coalesce(func.stddev_pop(Transaction.amount), 0),
                func.count(Transaction.id))
         .where(Transaction.user_id == user_id, Transaction.transaction_type == "EXPENSE",
                Transaction.transaction_date < before,
                Transaction.transaction_date >= before - timedelta(days=HISTORY_DAYS), group_col.is_not(None))
         .group_by(group_col))
    return {r[0]: (D(r[1]), D(r[2]), int(r[3])) for r in session.execute(q).all()}


def detect_anomalies(session: Session, user_id: int, lookback_days: int = 30, today: date | None = None) -> list[dict]:
    today = today or date.today()
    window_start = today - timedelta(days=lookback_days)
    merchant_key = func.lower(Transaction.merchant)
    by_merchant = _stats(session, user_id, merchant_key, window_start)
    by_category = _stats(session, user_id, Transaction.category_id, window_start)

    candidates = session.execute(
        select(Transaction.id, Transaction.amount, Transaction.merchant, Transaction.category_id)
        .where(Transaction.user_id == user_id, Transaction.transaction_type == "EXPENSE",
               Transaction.transaction_date >= window_start, Transaction.transaction_date <= today)).all()

    # reset previous verdicts for the window, then re-score
    session.execute(update(Transaction).where(
        Transaction.user_id == user_id, Transaction.transaction_date >= window_start)
        .values(is_anomaly=False, anomaly_score=None, anomaly_reason=None, anomaly_detected_at=None))
    now, found = datetime.now(UTC), []
    for tx_id, amount, merchant, category_id in candidates:
        results = []
        if merchant and merchant.lower() in by_merchant:
            m = by_merchant[merchant.lower()]
            results.append(evaluate(D(amount), Baseline(*m, label=f"{merchant} purchases")))
        if category_id in by_category:
            c = by_category[category_id]
            results.append(evaluate(D(amount), Baseline(*c, label="purchases in this category")))
        best = max((r for r in results if r), key=lambda r: r.score, default=None)
        if best:
            session.execute(update(Transaction).where(Transaction.id == tx_id).values(
                is_anomaly=True, anomaly_score=best.score, anomaly_reason=best.reason, anomaly_detected_at=now))
            found.append({"transaction_id": tx_id, "score": best.score, "reason": best.reason})
    session.commit()
    return sorted(found, key=lambda r: r["score"], reverse=True)


def list_anomalies(session: Session, user_id: int, limit: int = 20, days: int = 90) -> list[dict]:
    since = date.today() - timedelta(days=days)
    rows = session.execute(
        select(Transaction).where(Transaction.user_id == user_id, Transaction.is_anomaly == True,  # noqa: E712
                                  Transaction.transaction_date >= since)
        .order_by(Transaction.anomaly_score.desc()).limit(limit)).scalars().all()
    return [{"transaction_id": t.id, "date": t.transaction_date, "merchant": t.merchant, "amount": t.amount,
             "score": t.anomaly_score, "reason": t.anomaly_reason} for t in rows]
