from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class ImportJob(SQLModel, table=True):
    __tablename__ = "import_jobs"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    account_id: int = Field(foreign_key="accounts.id")
    filename: str = Field(max_length=255)
    storage_path: str = Field(max_length=500)
    column_mapping: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False, server_default="{}"))
    status: str = Field(default="PENDING", max_length=12, index=True)
    total_rows: int = 0
    processed_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    duplicate_rows: int = 0
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
