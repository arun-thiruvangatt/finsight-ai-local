from sqlmodel import Session

from app.ai.tools.base import ToolArgs, register
from app.services import recurring_service


@register("get_recurring_expenses", "Detected recurring expenses (subscriptions, bills) with amount, frequency "
                                    "and confidence, largest first.", ToolArgs)
def get_recurring_expenses(session: Session, user_id: int, a: ToolArgs):
    items = recurring_service.list_recurring(session, user_id)
    monthly = sum((recurring_service.monthly_equivalent(i["average_amount"], i["frequency"]) for i in items), 0)
    return {"recurring": items, "estimated_monthly_total": monthly}
