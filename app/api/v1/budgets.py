from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.budget import BudgetCreate, BudgetRead, BudgetStatus, BudgetUpdate
from app.services import budget_service

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.post("", response_model=BudgetRead, status_code=201, summary="Create budget")
def create_budget(data: BudgetCreate, user: CurrentUser, session: SessionDep):
    return budget_service.create(session, user.id, data)


@router.get("", response_model=list[BudgetRead], summary="List budgets")
def list_budgets(user: CurrentUser, session: SessionDep, include_inactive: bool = False):
    return budget_service.list_budgets(session, user.id, active_only=not include_inactive)


@router.get("/status", response_model=list[BudgetStatus], summary="Spent / remaining / projection for every budget")
def all_status(user: CurrentUser, session: SessionDep):
    return budget_service.all_statuses(session, user.id)


@router.get("/{budget_id}", response_model=BudgetRead, summary="Get budget")
def get_budget(budget_id: int, user: CurrentUser, session: SessionDep):
    return budget_service.get(session, user.id, budget_id)


@router.get("/{budget_id}/status", response_model=BudgetStatus, summary="Status of one budget")
def budget_status(budget_id: int, user: CurrentUser, session: SessionDep):
    return budget_service.status_for(session, budget_service.get(session, user.id, budget_id))


@router.patch("/{budget_id}", response_model=BudgetRead, summary="Update budget")
def update_budget(budget_id: int, data: BudgetUpdate, user: CurrentUser, session: SessionDep):
    return budget_service.update(session, user.id, budget_id, data)


@router.delete("/{budget_id}", status_code=204, summary="Delete budget")
def delete_budget(budget_id: int, user: CurrentUser, session: SessionDep):
    budget_service.delete(session, user.id, budget_id)
    return Response(status_code=204)
