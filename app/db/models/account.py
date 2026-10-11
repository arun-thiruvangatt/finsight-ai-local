from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=120)
    account_type: str = Field(default="BANK", max_length=20)
    institution: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="INR", max_length=3)
    current_balance: Decimal = Field(default=Decimal("0.00"), sa_type=Numeric(14, 2))
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
