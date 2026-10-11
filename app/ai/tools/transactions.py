from datetime import date
from decimal import Decimal

from pydantic import Field
from sqlalchemy import select
from sqlmodel import Session

from app.ai.tools.base import ToolArgs, register
from app.db.models import Category
from app.services import category_service, transaction_service


class GetTransactionsArgs(ToolArgs):
    from_date: date | None = None
    to_date: date | None = None
    category: str | None = Field(default=None, description="Category name, e.g. 'Food'")
    merchant: str | None = None
    transaction_type: str | None = Field(default=None, pattern="^(INCOME|EXPENSE|TRANSFER)$")
    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    search: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class GetTransactionArgs(ToolArgs):
    transaction_id: int


def _row(t, names: dict[int, str]) -> dict:
    return {"id": t.id, "date": t.transaction_date, "merchant": t.merchant, "description": t.description,
            "amount": t.amount, "type": t.transaction_type, "category": names.get(t.category_id),
            "is_anomaly": t.is_anomaly}


def _names(session: Session, user_id: int) -> dict[int, str]:
    return {c.id: c.name for c in session.execute(select(Category).where(Category.user_id == user_id)).scalars()}


@register("get_transactions", "List the user's transactions, newest first, with optional filters. "
                              "Returns at most `limit` rows plus the total number matching.", GetTransactionsArgs)
def get_transactions(session: Session, user_id: int, a: GetTransactionsArgs):
    cat_ids = None
    if a.category:
        cat = category_service.find_by_name(session, user_id, a.category)
        cat_ids = category_service.descendant_ids(session, user_id, cat.id) if cat else [-1]
    f = transaction_service.TransactionFilters(
        from_date=a.from_date, to_date=a.to_date, category_ids=cat_ids, transaction_type=a.transaction_type,
        merchant=a.merchant, min_amount=a.min_amount, max_amount=a.max_amount, search=a.search)
    rows, total = transaction_service.list_transactions(session, user_id, f, 1, a.limit)
    names = _names(session, user_id)
    return {"total_matching": total, "returned": len(rows), "transactions": [_row(t, names) for t in rows]}


@register("get_transaction", "Get one transaction by id.", GetTransactionArgs)
def get_transaction(session: Session, user_id: int, a: GetTransactionArgs):
    return _row(transaction_service.get(session, user_id, a.transaction_id), _names(session, user_id))
