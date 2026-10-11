from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class FinancialGoal(SQLModel, table=True):
    __tablename__ = "financial_goals"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=120)
    target_amount: Decimal = Field(sa_type=Numeric(14, 2))
    current_amount: Decimal = Field(default=Decimal("0.00"), sa_type=Numeric(14, 2))
    target_date: date | None = None
    priority: str = Field(default="MEDIUM", max_length=10)
    status: str = Field(default="ACTIVE", max_length=12)
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
