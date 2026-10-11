from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.constants import AccountType
from app.schemas.common import Money, ORMModel
from app.utils.validators import validate_currency


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    account_type: AccountType = AccountType.BANK
    institution: str | None = Field(default=None, max_length=120)
    currency: str = "INR"
    current_balance: Decimal = Field(default=Decimal("0"), max_digits=14, decimal_places=2)

    @field_validator("currency")
    @classmethod
    def _cur(cls, v):
        return validate_currency(v)

    model_config = {"json_schema_extra": {"example": {
        "name": "HDFC Savings", "account_type": "BANK", "institution": "HDFC Bank",
        "currency": "INR", "current_balance": 50000}}}


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    account_type: AccountType | None = None
    institution: str | None = None
    is_active: bool | None = None
    current_balance: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)


class AccountRead(ORMModel):
    id: int
    name: str
    account_type: str
    institution: str | None
    currency: str
    current_balance: Money
    is_active: bool
    created_at: datetime
