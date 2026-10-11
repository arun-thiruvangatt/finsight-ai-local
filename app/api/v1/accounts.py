from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate
from app.services import account_service

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.post("", response_model=AccountRead, status_code=201, summary="Create account")
def create_account(data: AccountCreate, user: CurrentUser, session: SessionDep):
    return account_service.create(session, user.id, data)


@router.get("", response_model=list[AccountRead], summary="List my accounts")
def list_accounts(user: CurrentUser, session: SessionDep, include_inactive: bool = False):
    return account_service.list_accounts(session, user.id, include_inactive)


@router.get("/{account_id}", response_model=AccountRead, summary="Get account")
def get_account(account_id: int, user: CurrentUser, session: SessionDep):
    return account_service.get(session, user.id, account_id)


@router.patch("/{account_id}", response_model=AccountRead, summary="Update account")
def update_account(account_id: int, data: AccountUpdate, user: CurrentUser, session: SessionDep):
    return account_service.update(session, user.id, account_id, data)


@router.delete("/{account_id}", status_code=204, summary="Delete account (only if it has no transactions)")
def delete_account(account_id: int, user: CurrentUser, session: SessionDep):
    account_service.delete(session, user.id, account_id)
    return Response(status_code=204)
