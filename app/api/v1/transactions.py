from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, SessionDep
from app.core.constants import TransactionType
from app.schemas.common import Page
from app.schemas.transaction import TransactionCreate, TransactionRead, TransactionUpdate
from app.services import transaction_service
from app.services.transaction_service import TransactionFilters

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionRead, status_code=201, summary="Create transaction")
def create_transaction(data: TransactionCreate, user: CurrentUser, session: SessionDep):
    return transaction_service.create(session, user.id, data)


@router.get("", response_model=Page[TransactionRead], summary="List transactions (filter, search, sort, paginate)")
def list_transactions(
    user: CurrentUser, session: SessionDep,
    from_date: date | None = None, to_date: date | None = None, account_id: int | None = None,
    category_id: int | None = None, transaction_type: TransactionType | None = None,
    merchant: str | None = None, min_amount: Decimal | None = Query(default=None, ge=0),
    max_amount: Decimal | None = Query(default=None, ge=0), is_anomaly: bool | None = None,
    is_recurring: bool | None = None, search: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
    sort: Literal["transaction_date", "amount", "merchant", "created_at"] = "transaction_date",
    order: Literal["asc", "desc"] = "desc",
):
    f = TransactionFilters(
        from_date=from_date, to_date=to_date, account_id=account_id, category_id=category_id,
        transaction_type=transaction_type.value if transaction_type else None, merchant=merchant,
        min_amount=min_amount, max_amount=max_amount, is_anomaly=is_anomaly, is_recurring=is_recurring,
        search=search)
    items, total = transaction_service.list_transactions(session, user.id, f, page, page_size, sort, order)
    return Page[TransactionRead](items=[TransactionRead.model_validate(i) for i in items], total=total,
                                 page=page, page_size=page_size)


@router.get("/{transaction_id}", response_model=TransactionRead, summary="Get transaction")
def get_transaction(transaction_id: int, user: CurrentUser, session: SessionDep):
    return transaction_service.get(session, user.id, transaction_id)


@router.patch("/{transaction_id}", response_model=TransactionRead, summary="Update transaction")
def update_transaction(transaction_id: int, data: TransactionUpdate, user: CurrentUser, session: SessionDep):
    return transaction_service.update(session, user.id, transaction_id, data)


@router.delete("/{transaction_id}", status_code=204, summary="Delete transaction")
def delete_transaction(transaction_id: int, user: CurrentUser, session: SessionDep):
    transaction_service.delete(session, user.id, transaction_id)
    return Response(status_code=204)
