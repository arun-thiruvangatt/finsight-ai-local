from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(max_length=255)
    filename: str = Field(max_length=255)
    doc_type: str = Field(default="NOTE", max_length=16)
    status: str = Field(default="PENDING", max_length=12)
    storage_path: str = Field(max_length=500)
    chunk_count: int = 0
    error_message: str | None = None
    # attribute is `meta` because `metadata` is reserved by SQLAlchemy declarative.
    meta: dict = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"))
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
