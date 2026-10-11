from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Budget(SQLModel, table=True):
    __tablename__ = "budgets"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    name: str = Field(max_length=120)
    amount: Decimal = Field(sa_type=Numeric(14, 2))
    period: str = Field(default="MONTHLY", max_length=10)
    start_date: date
    end_date: date | None = None
    alert_threshold: Decimal = Field(default=Decimal("80"), sa_type=Numeric(5, 2))
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
