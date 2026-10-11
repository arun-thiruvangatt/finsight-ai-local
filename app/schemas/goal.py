from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.constants import GoalPriority, GoalStatus
from app.schemas.common import Money, NonNegativeMoney, ORMModel, PositiveMoney


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    target_amount: PositiveMoney
    current_amount: NonNegativeMoney = 0
    target_date: date | None = None
    priority: GoalPriority = GoalPriority.MEDIUM


class GoalUpdate(BaseModel):
    name: str | None = None
    target_amount: PositiveMoney | None = None
    current_amount: NonNegativeMoney | None = None
    target_date: date | None = None
    priority: GoalPriority | None = None
    status: GoalStatus | None = None


class GoalRead(ORMModel):
    id: int
    name: str
    target_amount: Money
    current_amount: Money
    target_date: date | None
    priority: str
    status: str
    created_at: datetime


class GoalProgress(BaseModel):
    goal_id: int
    name: str
    target_amount: Money
    current_amount: Money
    remaining_amount: Money
    progress_percentage: Money
    months_left: int | None
    required_monthly_contribution: Money | None
    avg_monthly_savings: Money
    safe_allocation_estimate: Money
    projected_completion: str | None
    projection_note: str
    on_track: bool | None
