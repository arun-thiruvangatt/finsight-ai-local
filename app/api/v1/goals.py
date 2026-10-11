from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.goal import GoalCreate, GoalProgress, GoalRead, GoalUpdate
from app.services import goal_service

router = APIRouter(prefix="/goals", tags=["Goals"])


@router.post("", response_model=GoalRead, status_code=201, summary="Create goal")
def create_goal(data: GoalCreate, user: CurrentUser, session: SessionDep):
    return goal_service.create(session, user.id, data)


@router.get("", response_model=list[GoalRead], summary="List goals")
def list_goals(user: CurrentUser, session: SessionDep):
    return goal_service.list_goals(session, user.id)


@router.get("/progress", response_model=list[GoalProgress], summary="Progress and projections for all active goals")
def all_progress(user: CurrentUser, session: SessionDep):
    return [goal_service.progress(session, g) for g in goal_service.list_goals(session, user.id)
            if g.status == "ACTIVE"]


@router.get("/{goal_id}", response_model=GoalRead, summary="Get goal")
def get_goal(goal_id: int, user: CurrentUser, session: SessionDep):
    return goal_service.get(session, user.id, goal_id)


@router.get("/{goal_id}/progress", response_model=GoalProgress, summary="Progress of one goal")
def goal_progress(goal_id: int, user: CurrentUser, session: SessionDep):
    return goal_service.progress(session, goal_service.get(session, user.id, goal_id))


@router.patch("/{goal_id}", response_model=GoalRead, summary="Update goal")
def update_goal(goal_id: int, data: GoalUpdate, user: CurrentUser, session: SessionDep):
    return goal_service.update(session, user.id, goal_id, data)


@router.delete("/{goal_id}", status_code=204, summary="Delete goal")
def delete_goal(goal_id: int, user: CurrentUser, session: SessionDep):
    goal_service.delete(session, user.id, goal_id)
    return Response(status_code=204)
