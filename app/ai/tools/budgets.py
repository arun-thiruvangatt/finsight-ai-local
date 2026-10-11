from pydantic import Field
from sqlmodel import Session

from app.ai.tools.base import ToolArgs, register
from app.services import budget_service


class BudgetArgs(ToolArgs):
    category: str | None = Field(default=None, description="Only budgets for this category name")


@register("get_budget_status", "Status of the user's active budgets: budget, spent, remaining, usage %, projected "
                               "month-end spending (an estimate) and warnings.", BudgetArgs)
def get_budget_status(session: Session, user_id: int, a: BudgetArgs):
    items = budget_service.all_statuses(session, user_id)
    if a.category:
        items = [i for i in items if i["category"] and a.category.lower() in i["category"].lower()]
    return {"budgets": items}
