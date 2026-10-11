from sqlalchemy import func
from sqlmodel import Session, select

from app.core.exceptions import ConflictError
from app.db.models import Account, Transaction
from app.schemas.account import AccountCreate, AccountUpdate
from app.services.common import get_owned


def create(session: Session, user_id: int, data: AccountCreate) -> Account:
    acc = Account(user_id=user_id, name=data.name.strip(), account_type=data.account_type.value,
                  institution=data.institution, currency=data.currency, current_balance=data.current_balance)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def list_accounts(session: Session, user_id: int, include_inactive: bool = False) -> list[Account]:
    q = select(Account).where(Account.user_id == user_id).order_by(Account.name)
    if not include_inactive:
        q = q.where(Account.is_active == True)  # noqa: E712
    return list(session.exec(q))


def get(session: Session, user_id: int, account_id: int) -> Account:
    return get_owned(session, Account, account_id, user_id, "Account")


def update(session: Session, user_id: int, account_id: int, data: AccountUpdate) -> Account:
    acc = get(session, user_id, account_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(acc, k, v.value if hasattr(v, "value") else v)
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def delete(session: Session, user_id: int, account_id: int) -> None:
    acc = get(session, user_id, account_id)
    count = session.execute(select(func.count()).select_from(Transaction)
                            .where(Transaction.account_id == acc.id)).scalar_one()
    if count:
        raise ConflictError("Account has transactions. Deactivate it instead of deleting.",
                            code="ACCOUNT_HAS_TRANSACTIONS")
    session.delete(acc)
    session.commit()
