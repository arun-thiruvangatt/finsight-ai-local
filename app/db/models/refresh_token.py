from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    jti: str = Field(unique=True, index=True, max_length=64)
    token_hash: str = Field(max_length=64)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True))
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
