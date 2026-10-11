from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_logs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    action: str = Field(max_length=64, index=True)
    entity: str | None = Field(default=None, max_length=64)
    entity_id: str | None = Field(default=None, max_length=64)
    meta: dict = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"))
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
