from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.core.exceptions import AppError
from app.db.models import Budget, Category
from app.schemas.budget import BudgetCreate, BudgetUpdate
from app.services import analytics_service, category_service
from app.services.common import get_owned
from app.utils.dates import month_bounds, week_bounds
from app.utils.money import ZERO, format_inr, percentage, quantize


def resolve_window(budget: Budget, today: date) -> tuple[date, date]:
    """Half-open window [start, end) the budget applies to *today*."""
    if budget.period == "MONTHLY":
        return month_bounds(today)
    if budget.period == "WEEKLY":
        return week_bounds(today)
    return budget.start_date, (budget.end_date or budget.start_date) + timedelta(days=1)


def project_spending(spent: Decimal, start: date, end: date, today: date) -> Decimal:
    """Linear run-rate projection to the end of the window. An ESTIMATE, not a forecast."""
    total_days = (end - start).days
    if today >= end:
        return quantize(spent)
    if today < start or total_days <= 0:
        return ZERO
    elapsed = (today - start).days + 1
    return quantize(spent / elapsed * total_days)


def build_warnings(budget_amount: Decimal, spent: Decimal, projected: Decimal, threshold: Decimal) -> list[str]:
    usage = percentage(spent, budget_amount)
    out = []
    if spent > budget_amount:
        out.append(f"Budget exceeded by {format_inr(spent - budget_amount)}.")
    elif usage >= threshold:
        out.append(f"{usage}% of the budget is used (alert threshold {threshold}%).")
    if spent <= budget_amount < projected:
        out.append(f"Estimate: at the current pace you would spend about {format_inr(projected)}, "
                   f"above the budget of {format_inr(budget_amount)}.")
    return out


def status_for(session: Session, budget: Budget, today: date | None = None) -> dict:
    today = today or date.today()
    start, end = resolve_window(budget, today)
    ids, cat_name = None, None
    if budget.category_id:
        ids = category_service.descendant_ids(session, budget.user_id, budget.category_id)
        cat = session.get(Category, budget.category_id)
        cat_name = cat.name if cat else None
    if ids is None:
        spent = analytics_service.sum_amount(session, budget.user_id, "EXPENSE", start, end)
    else:
        spent = analytics_service.sum_amount(session, budget.user_id, "EXPENSE", start, end, ids)
    projected = project_spending(spent, start, end, today)
    return {
        "budget_id": budget.id, "name": budget.name, "category": cat_name, "period": budget.period,
        "window_start": start, "window_end": end - timedelta(days=1),
        "budget": budget.amount, "spent": spent, "remaining": budget.amount - spent,
        "usage_percentage": percentage(spent, budget.amount), "projected_spending": projected,
        "projected_over_budget": projected > budget.amount,
        "warnings": build_warnings(budget.amount, spent, projected, budget.alert_threshold),
    }


def _validate(session: Session, user_id: int, category_id: int | None) -> None:
    if category_id is not None:
        get_owned(session, Category, category_id, user_id, "Category")


def create(session: Session, user_id: int, data: BudgetCreate) -> Budget:
    _validate(session, user_id, data.category_id)
    b = Budget(user_id=user_id, category_id=data.category_id, name=data.name, amount=data.amount,
               period=data.period.value, start_date=data.start_date, end_date=data.end_date,
               alert_threshold=data.alert_threshold)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def list_budgets(session: Session, user_id: int, active_only: bool = True) -> list[Budget]:
    q = select(Budget).where(Budget.user_id == user_id).order_by(Budget.name)
    if active_only:
        q = q.where(Budget.is_active == True)  # noqa: E712
    return list(session.exec(q))


def get(session: Session, user_id: int, budget_id: int) -> Budget:
    return get_owned(session, Budget, budget_id, user_id, "Budget")


def update(session: Session, user_id: int, budget_id: int, data: BudgetUpdate) -> Budget:
    b = get(session, user_id, budget_id)
    changes = data.model_dump(exclude_unset=True)
    if "category_id" in changes:
        _validate(session, user_id, changes["category_id"])
    for k, v in changes.items():
        if v is None and k in {"name", "amount", "period", "start_date", "alert_threshold", "is_active"}:
            raise AppError(f"{k} cannot be null.", code="VALIDATION_ERROR", status_code=422)
        setattr(b, k, v.value if hasattr(v, "value") else v)
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def delete(session: Session, user_id: int, budget_id: int) -> None:
    session.delete(get(session, user_id, budget_id))
    session.commit()


def all_statuses(session: Session, user_id: int, today: date | None = None) -> list[dict]:
    return [status_for(session, b, today) for b in list_budgets(session, user_id)]

