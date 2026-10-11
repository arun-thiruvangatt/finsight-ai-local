from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    password_hash: str
    full_name: str = Field(max_length=200)
    currency: str = Field(default="INR", max_length=3)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    role: str = Field(default="USER", max_length=16)
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
