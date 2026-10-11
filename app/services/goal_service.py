import math
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from app.db.models import FinancialGoal
from app.schemas.goal import GoalCreate, GoalUpdate
from app.services import analytics_service
from app.services.common import get_owned
from app.utils.dates import add_months, month_str
from app.utils.money import ZERO, percentage, quantize

SAFE_ALLOCATION_RATIO = Decimal("0.8")  # keep a 20% buffer of average savings


def create(session: Session, user_id: int, data: GoalCreate) -> FinancialGoal:
    g = FinancialGoal(user_id=user_id, name=data.name, target_amount=data.target_amount,
                      current_amount=data.current_amount, target_date=data.target_date, priority=data.priority.value)
    session.add(g)
    session.commit()
    session.refresh(g)
    return g


def list_goals(session: Session, user_id: int) -> list[FinancialGoal]:
    return list(session.exec(select(FinancialGoal).where(FinancialGoal.user_id == user_id)
                             .order_by(FinancialGoal.target_date.is_(None), FinancialGoal.target_date)))


def get(session: Session, user_id: int, goal_id: int) -> FinancialGoal:
    return get_owned(session, FinancialGoal, goal_id, user_id, "Goal")


def update(session: Session, user_id: int, goal_id: int, data: GoalUpdate) -> FinancialGoal:
    g = get(session, user_id, goal_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is None and k != "target_date":
            continue
        setattr(g, k, v.value if hasattr(v, "value") else v)
    if g.current_amount >= g.target_amount and g.status == "ACTIVE":
        g.status = "COMPLETED"
    session.add(g)
    session.commit()
    session.refresh(g)
    return g


def delete(session: Session, user_id: int, goal_id: int) -> None:
    session.delete(get(session, user_id, goal_id))
    session.commit()


def months_until(target: date, today: date) -> int:
    if target <= today:
        return 0
    return max(1, math.ceil((target - today).days / 30.4375))


def average_monthly_savings(session: Session, user_id: int, today: date, months: int = 3) -> tuple[Decimal, int]:
    """Average of (income - expenses) over the last `months` COMPLETED months that contain data."""
    last_full = add_months(today.replace(day=1), -1)
    points = analytics_service.get_cashflow(session, user_id, months, month_str(last_full))
    active = [p for p in points if p["income"] or p["expenses"]]
    if not active:
        return ZERO, 0
    return quantize(sum((p["net"] for p in active), ZERO) / len(active)), len(active)


def progress(session: Session, goal: FinancialGoal, today: date | None = None) -> dict:
    today = today or date.today()
    remaining = max(goal.target_amount - goal.current_amount, ZERO)
    avg, used = average_monthly_savings(session, goal.user_id, today)
    left = months_until(goal.target_date, today) if goal.target_date else None
    required = quantize(remaining / max(left, 1)) if left is not None and remaining > 0 else (ZERO if left is not None else None)

    projected, on_track = None, None
    if remaining == 0:
        projected, on_track = "completed", True
    elif avg > 0:
        needed = math.ceil(remaining / avg)
        projected = month_str(add_months(today.replace(day=1), needed))
        if goal.target_date:
            on_track = projected <= month_str(goal.target_date)
    note = (f"Estimate based on your average monthly savings over the last {used} completed month(s); "
            "not a guarantee." if used else "Not enough history to estimate a completion date.")
    return {
        "goal_id": goal.id, "name": goal.name, "target_amount": goal.target_amount,
        "current_amount": goal.current_amount, "remaining_amount": remaining,
        "progress_percentage": min(percentage(goal.current_amount, goal.target_amount), Decimal("100")),
        "months_left": left, "required_monthly_contribution": required, "avg_monthly_savings": avg,
        "safe_allocation_estimate": quantize(max(avg, ZERO) * SAFE_ALLOCATION_RATIO),
        "projected_completion": projected, "projection_note": note, "on_track": on_track,
    }
