from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class RecurringTransaction(SQLModel, table=True):
    __tablename__ = "recurring_transactions"
    __table_args__ = (UniqueConstraint("user_id", "merchant", name="uq_recurring_user_merchant"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    merchant: str = Field(max_length=200)
    average_amount: Decimal = Field(sa_type=Numeric(14, 2))
    frequency: str = Field(max_length=10)
    next_expected_date: date | None = None
    last_transaction_date: date | None = None
    confidence: float = 0.0
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
