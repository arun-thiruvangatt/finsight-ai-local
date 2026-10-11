from datetime import datetime

from sqlalchemy import Column, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class AIInsight(SQLModel, table=True):
    __tablename__ = "ai_insights"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_insight_user_key"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    insight_type: str = Field(max_length=32, index=True)
    title: str = Field(max_length=200)
    description: str
    severity: str = Field(default="INFO", max_length=10)
    data: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default="{}"))
    dedupe_key: str = Field(max_length=200)
    generated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    expires_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
