from decimal import Decimal
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

# Output money: Decimal inside the app, JSON number at the edge.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
# Input money: strictly positive, max 2 decimal places.
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class Message(BaseModel):
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
