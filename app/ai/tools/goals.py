from pydantic import Field
from sqlmodel import Session

from app.ai.tools.base import ToolArgs, register
from app.services import goal_service


class GoalArgs(ToolArgs):
    goal_name: str | None = Field(default=None, description="Part of the goal name; omit for all active goals")


@register("get_goal_status", "Progress of financial goals: remaining amount, required monthly contribution, average "
                             "monthly savings, a safe allocation estimate and projected completion (estimate).", GoalArgs)
def get_goal_status(session: Session, user_id: int, a: GoalArgs):
    goals = [g for g in goal_service.list_goals(session, user_id) if g.status == "ACTIVE"]
    if a.goal_name:
        goals = [g for g in goals if a.goal_name.lower() in g.name.lower()]
    return {"goals": [goal_service.progress(session, g) for g in goals]}
