from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.core.constants import BudgetPeriod
from app.schemas.common import Money, ORMModel, PositiveMoney


class BudgetCreate(BaseModel):
    category_id: int | None = None
    name: str = Field(min_length=1, max_length=120)
    amount: PositiveMoney
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    start_date: date
    end_date: date | None = None
    alert_threshold: Decimal = Field(default=Decimal("80"), ge=1, le=100, max_digits=5, decimal_places=2)

    @model_validator(mode="after")
    def _custom_needs_end(self):
        if self.period == BudgetPeriod.CUSTOM and not self.end_date:
            raise ValueError("CUSTOM budgets require end_date")
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class BudgetUpdate(BaseModel):
    category_id: int | None = None
    name: str | None = None
    amount: PositiveMoney | None = None
    period: BudgetPeriod | None = None
    start_date: date | None = None
    end_date: date | None = None
    alert_threshold: Decimal | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class BudgetRead(ORMModel):
    id: int
    category_id: int | None
    name: str
    amount: Money
    period: str
    start_date: date
    end_date: date | None
    alert_threshold: Money
    is_active: bool
    created_at: datetime


class BudgetStatus(BaseModel):
    budget_id: int
    name: str
    category: str | None
    period: str
    window_start: date
    window_end: date
    budget: Money
    spent: Money
    remaining: Money
    usage_percentage: Money
    projected_spending: Money
    projected_over_budget: bool
    warnings: list[str]
