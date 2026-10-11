import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlmodel import Session

from app.core.exceptions import AppError
from app.db.models import Account, Category, Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services import categorization_service
from app.services.common import get_owned
from app.utils.money import ZERO

SORTABLE = {"transaction_date": Transaction.transaction_date, "amount": Transaction.amount,
            "merchant": Transaction.merchant, "created_at": Transaction.created_at}


@dataclass
class TransactionFilters:
    from_date: date | None = None
    to_date: date | None = None
    account_id: int | None = None
    category_id: int | None = None
    category_ids: list[int] | None = None
    transaction_type: str | None = None
    merchant: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    is_anomaly: bool | None = None
    is_recurring: bool | None = None
    search: str | None = None


def balance_delta(transaction_type: str, amount: Decimal) -> Decimal:
    if transaction_type == "INCOME":
        return amount
    if transaction_type == "EXPENSE":
        return -amount
    return ZERO


def make_fingerprint(user_id: int, account_id: int, tx_date: date, amount: Decimal, text: str,
                     reference: str | None, occurrence: int = 0) -> str:
    """Deterministic duplicate key. `occurrence` distinguishes genuinely identical rows inside
    one file (two identical coffees on one day) while keeping re-imports idempotent."""
    base = "|".join([str(user_id), str(account_id), tx_date.isoformat(), f"{amount:.2f}",
                     " ".join((text or "").lower().split()), (reference or "").strip().lower(), str(occurrence)])
    return hashlib.sha256(base.encode()).hexdigest()


def _filter_clauses(user_id: int, f: TransactionFilters) -> list:
    c = [Transaction.user_id == user_id]  # ownership is always the first predicate
    if f.from_date:
        c.append(Transaction.transaction_date >= f.from_date)
    if f.to_date:
        c.append(Transaction.transaction_date <= f.to_date)
    if f.account_id:
        c.append(Transaction.account_id == f.account_id)
    if f.category_id:
        c.append(Transaction.category_id == f.category_id)
    if f.category_ids is not None:
        c.append(Transaction.category_id.in_(f.category_ids))
    if f.transaction_type:
        c.append(Transaction.transaction_type == f.transaction_type)
    if f.merchant:
        c.append(Transaction.merchant.ilike(f"%{f.merchant}%"))
    if f.min_amount is not None:
        c.append(Transaction.amount >= f.min_amount)
    if f.max_amount is not None:
        c.append(Transaction.amount <= f.max_amount)
    if f.is_anomaly is not None:
        c.append(Transaction.is_anomaly == f.is_anomaly)
    if f.is_recurring is not None:
        c.append(Transaction.is_recurring == f.is_recurring)
    if f.search:
        like = f"%{f.search}%"
        c.append(or_(Transaction.merchant.ilike(like), Transaction.description.ilike(like),
                     Transaction.reference.ilike(like)))
    return c


def list_transactions(session: Session, user_id: int, f: TransactionFilters, page: int = 1, page_size: int = 25,
                      sort: str = "transaction_date", order: str = "desc") -> tuple[list[Transaction], int]:
    if sort not in SORTABLE:
        raise AppError(f"Cannot sort by '{sort}'.", code="INVALID_SORT")
    clauses = _filter_clauses(user_id, f)
    total = session.execute(select(func.count()).select_from(Transaction).where(*clauses)).scalar_one()
    col = SORTABLE[sort]
    primary = col.asc() if order == "asc" else col.desc()
    q = (select(Transaction).where(*clauses)
         .order_by(primary, Transaction.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return list(session.execute(q).scalars()), total


def get(session: Session, user_id: int, tx_id: int) -> Transaction:
    return get_owned(session, Transaction, tx_id, user_id, "Transaction")


def _active_account(session: Session, user_id: int, account_id: int) -> Account:
    acc = get_owned(session, Account, account_id, user_id, "Account")
    if not acc.is_active:
        raise AppError("Account is inactive.", code="ACCOUNT_INACTIVE")
    return acc


def _check_category(session: Session, user_id: int, category_id: int | None) -> None:
    if category_id is not None:
        get_owned(session, Category, category_id, user_id, "Category")


def _apply_balance(account: Account, delta: Decimal) -> None:
    account.current_balance = (account.current_balance or ZERO) + delta


def create(session: Session, user_id: int, data: TransactionCreate) -> Transaction:
    account = _active_account(session, user_id, data.account_id)
    _check_category(session, user_id, data.category_id)
    tx = Transaction(
        user_id=user_id, account_id=account.id, category_id=data.category_id, amount=data.amount,
        transaction_type=data.transaction_type.value, merchant=data.merchant, description=data.description,
        transaction_date=data.transaction_date, reference=data.reference, currency=data.currency or account.currency,
        ai_category_source="manual" if data.category_id else None,
    )
    session.add(tx)
    session.flush()
    if tx.category_id is None:
        categorization_service.categorize_by_rules(session, user_id, tx_ids=[tx.id])
    _apply_balance(account, balance_delta(tx.transaction_type, tx.amount))
    session.add(account)
    session.commit()
    session.refresh(tx)
    return tx


def update(session: Session, user_id: int, tx_id: int, data: TransactionUpdate) -> Transaction:
    tx = get(session, user_id, tx_id)
    changes = data.model_dump(exclude_unset=True)
    old_account = get_owned(session, Account, tx.account_id, user_id, "Account")
    _apply_balance(old_account, -balance_delta(tx.transaction_type, tx.amount))
    session.add(old_account)

    if "account_id" in changes and changes["account_id"] is not None:
        _active_account(session, user_id, changes["account_id"])
    if "category_id" in changes:
        _check_category(session, user_id, changes["category_id"])
        tx.ai_category_source = "manual" if changes["category_id"] else None
        tx.ai_category_confidence = None
    for k, v in changes.items():
        if k in {"account_id", "amount", "transaction_type", "transaction_date"} and v is None:
            continue
        setattr(tx, k, v.value if hasattr(v, "value") else v)
    tx.fingerprint = None  # edited rows no longer represent the imported original

    new_account = get_owned(session, Account, tx.account_id, user_id, "Account")
    _apply_balance(new_account, balance_delta(tx.transaction_type, tx.amount))
    session.add_all([tx, new_account])
    session.commit()
    session.refresh(tx)
    return tx


def delete(session: Session, user_id: int, tx_id: int) -> None:
    tx = get(session, user_id, tx_id)
    account = get_owned(session, Account, tx.account_id, user_id, "Account")
    _apply_balance(account, -balance_delta(tx.transaction_type, tx.amount))
    session.add(account)
    session.delete(tx)
    session.commit()
