from datetime import date

from pydantic import Field
from sqlmodel import Session

from app.ai.tools.base import MONTH_PATTERN, ToolArgs, register, resolve_range
from app.services import analytics_service as an
from app.utils.dates import month_str, previous_month


class MonthArgs(ToolArgs):
    month: str | None = Field(default=None, pattern=MONTH_PATTERN, description="YYYY-MM, default current month")


class RangeArgs(MonthArgs):
    from_date: date | None = None
    to_date: date | None = None


class CategoryArgs(RangeArgs):
    category: str = Field(description="Category name such as 'Food' or 'Transport'")


class TrendArgs(ToolArgs):
    category: str | None = Field(default=None, description="Optional category; omit for total spending")
    months: int = Field(default=6, ge=2, le=24)


class CashflowArgs(ToolArgs):
    months: int = Field(default=6, ge=1, le=24)


class CompareArgs(ToolArgs):
    previous_month: str | None = Field(default=None, pattern=MONTH_PATTERN)
    current_month: str | None = Field(default=None, pattern=MONTH_PATTERN)


class MerchantArgs(RangeArgs):
    limit: int = Field(default=10, ge=1, le=25)


@register("get_monthly_summary", "Income, expenses, savings and savings rate for one month.", MonthArgs)
def get_monthly_summary(session: Session, user_id: int, a: MonthArgs):
    return an.get_monthly_summary(session, user_id, a.month or month_str(date.today()))


@register("get_category_expenses", "Total spent in a category (including sub-categories) for a month or date range, "
                                   "with sub-category breakdown.", CategoryArgs)
def get_category_expenses(session: Session, user_id: int, a: CategoryArgs):
    start, end, label = resolve_range(a.month, a.from_date, a.to_date)
    return {"period": label, **an.get_category_expenses(session, user_id, a.category, start, end)}


@register("get_category_trends", "Monthly spending over the last N months, for one category or in total.", TrendArgs)
def get_category_trends(session: Session, user_id: int, a: TrendArgs):
    pts = an.get_monthly_trends(session, user_id, a.months, month_str(date.today()), a.category)
    return {"category": a.category or "All spending", "months": pts}


@register("get_income_summary", "Total income and its sources for a month or date range.", RangeArgs)
def get_income_summary(session: Session, user_id: int, a: RangeArgs):
    start, end, label = resolve_range(a.month, a.from_date, a.to_date)
    return {"period": label, **an.get_income_summary(session, user_id, start, end)}


@register("get_cashflow", "Income, expenses and net cash flow per month for the last N months.", CashflowArgs)
def get_cashflow(session: Session, user_id: int, a: CashflowArgs):
    return {"months": an.get_cashflow(session, user_id, a.months, month_str(date.today()))}


@register("compare_months", "Compare spending between two months with the categories that changed most. "
                            "Defaults to previous month vs current month.", CompareArgs)
def compare_months(session: Session, user_id: int, a: CompareArgs):
    cur = a.current_month or month_str(date.today())
    prev = a.previous_month or previous_month(cur)
    return an.compare_months(session, user_id, prev, cur)


@register("get_top_merchants", "Merchants where the user spent the most in a month or date range.", MerchantArgs)
def get_top_merchants(session: Session, user_id: int, a: MerchantArgs):
    start, end, label = resolve_range(a.month, a.from_date, a.to_date)
    return {"period": label, "merchants": an.get_top_merchants(session, user_id, start, end, a.limit)}
