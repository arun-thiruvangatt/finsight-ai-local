from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=120)
    parent_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    category_type: str = Field(default="EXPENSE", max_length=16)
    is_system: bool = False
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
