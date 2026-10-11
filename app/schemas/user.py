from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from app.schemas.common import ORMModel
from app.utils.validators import validate_currency, validate_timezone


class UserRead(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    currency: str
    timezone: str
    role: str
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = None
    currency: str | None = None
    timezone: str | None = None

    @field_validator("currency")
    @classmethod
    def _cur(cls, v):
        return validate_currency(v) if v else v

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        return validate_timezone(v) if v else v
