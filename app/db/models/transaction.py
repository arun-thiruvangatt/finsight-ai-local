from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.db.models.base import utcnow


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index("ix_transactions_user_category_date", "user_id", "category_id", "transaction_date"),
        Index("ix_transactions_user_merchant", "user_id", "merchant"),
        # Duplicate protection enforced by the database (NULL fingerprints = manual entries, never equal).
        UniqueConstraint("user_id", "fingerprint", name="uq_transactions_user_fingerprint"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    category_id: int | None = Field(default=None, foreign_key="categories.id", index=True)
    # Always stored positive; transaction_type carries the direction.
    amount: Decimal = Field(sa_type=Numeric(14, 2))
    transaction_type: str = Field(max_length=16)
    merchant: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    transaction_date: date = Field(index=True)
    reference: str | None = Field(default=None, max_length=200)
    currency: str = Field(default="INR", max_length=3)

    is_recurring: bool = False
    is_anomaly: bool = False
    anomaly_score: float | None = None
    anomaly_reason: str | None = Field(default=None, max_length=500)
    anomaly_detected_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    ai_category_confidence: float | None = None
    ai_category_source: str | None = Field(default=None, max_length=16)  # rule | llm | manual

    fingerprint: str | None = Field(default=None, max_length=80)
    import_job_id: int | None = Field(default=None, foreign_key="import_jobs.id", index=True)

    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True),
                                 sa_column_kwargs={"onupdate": utcnow})
