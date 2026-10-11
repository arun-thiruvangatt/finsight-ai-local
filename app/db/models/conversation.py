from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(default="New conversation", max_length=200)
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))


class ConversationMessage(SQLModel, table=True):
    __tablename__ = "conversation_messages"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    role: str = Field(max_length=12)
    content: str
    meta: dict = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default="{}"))
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
