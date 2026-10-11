from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.core.constants import TransactionType
from app.schemas.common import Money, ORMModel, PositiveMoney
from app.utils.validators import validate_currency


class TransactionCreate(BaseModel):
    account_id: int
    category_id: int | None = None
    amount: PositiveMoney
    transaction_type: TransactionType
    merchant: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    transaction_date: date
    reference: str | None = Field(default=None, max_length=200)
    currency: str | None = None

    @field_validator("currency")
    @classmethod
    def _cur(cls, v):
        return validate_currency(v) if v else v

    model_config = {"json_schema_extra": {"example": {
        "account_id": 1, "category_id": 3, "amount": "250.00", "transaction_type": "EXPENSE",
        "merchant": "Swiggy", "description": "Dinner", "transaction_date": "2026-10-03"}}}


class TransactionUpdate(BaseModel):
    account_id: int | None = None
    category_id: int | None = None
    amount: PositiveMoney | None = None
    transaction_type: TransactionType | None = None
    merchant: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    transaction_date: date | None = None
    reference: str | None = Field(default=None, max_length=200)


class TransactionRead(ORMModel):
    id: int
    account_id: int
    category_id: int | None
    amount: Money
    transaction_type: str
    merchant: str | None
    description: str | None
    transaction_date: date
    reference: str | None
    currency: str
    is_recurring: bool
    is_anomaly: bool
    anomaly_score: float | None
    anomaly_reason: str | None
    ai_category_confidence: float | None
    ai_category_source: str | None
    created_at: datetime
