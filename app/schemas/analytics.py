from pydantic import BaseModel

from app.schemas.common import Money


class MonthlySummary(BaseModel):
    month: str
    income: Money
    expenses: Money
    savings: Money
    savings_rate: Money


class CategoryBreakdownItem(BaseModel):
    category_id: int | None
    category: str
    amount: Money
    percentage: Money
    transaction_count: int


class CashflowPoint(BaseModel):
    month: str
    income: Money
    expenses: Money
    net: Money


class MerchantItem(BaseModel):
    merchant: str
    amount: Money
    transaction_count: int


class TrendPoint(BaseModel):
    month: str
    expenses: Money
    income: Money
