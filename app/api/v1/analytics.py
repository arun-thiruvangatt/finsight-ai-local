from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.analytics import CashflowPoint, CategoryBreakdownItem, MerchantItem, MonthlySummary, TrendPoint
from app.services import analytics_service as an
from app.utils.dates import month_bounds, month_str

router = APIRouter(prefix="/analytics", tags=["Analytics"])
MonthQ = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM, default current month")


def _range(month: str | None, from_date: date | None, to_date: date | None) -> tuple[date, date]:
    if from_date or to_date:
        start = from_date or (to_date - timedelta(days=30))
        return start, (to_date or date.today()) + timedelta(days=1)
    return month_bounds(month or month_str(date.today()))


@router.get("/monthly", response_model=MonthlySummary, summary="Income, expenses, savings for a month")
def monthly(user: CurrentUser, session: SessionDep, month: str | None = MonthQ):
    return an.get_monthly_summary(session, user.id, month or month_str(date.today()))


@router.get("/categories", response_model=list[CategoryBreakdownItem], summary="Spending by category")
def categories(user: CurrentUser, session: SessionDep, month: str | None = MonthQ, from_date: date | None = None,
               to_date: date | None = None, level: Literal["top", "leaf"] = "top",
               transaction_type: Literal["EXPENSE", "INCOME"] = "EXPENSE"):
    start, end = _range(month, from_date, to_date)
    return an.get_category_breakdown(session, user.id, start, end, transaction_type, level)


@router.get("/cashflow", response_model=list[CashflowPoint], summary="Monthly income vs expenses")
def cashflow(user: CurrentUser, session: SessionDep, months: int = Query(6, ge=1, le=36)):
    return an.get_cashflow(session, user.id, months, month_str(date.today()))


@router.get("/trends", response_model=list[TrendPoint], summary="Monthly spending trend (optionally one category)")
def trends(user: CurrentUser, session: SessionDep, months: int = Query(6, ge=2, le=36), category: str | None = None):
    return an.get_monthly_trends(session, user.id, months, month_str(date.today()), category)


@router.get("/merchants", response_model=list[MerchantItem], summary="Top merchants by spend")
def merchants(user: CurrentUser, session: SessionDep, month: str | None = MonthQ, from_date: date | None = None,
              to_date: date | None = None, limit: int = Query(10, ge=1, le=50)):
    start, end = _range(month, from_date, to_date)
    return an.get_top_merchants(session, user.id, start, end, limit)


@router.get("/daily", summary="Daily spending for a month")
def daily(user: CurrentUser, session: SessionDep, month: str | None = MonthQ):
    start, end = month_bounds(month or month_str(date.today()))
    return [{"date": r["date"], "amount": float(r["amount"])} for r in an.get_daily_spending(session, user.id, start, end)]


@router.get("/compare", summary="Compare two months")
def compare(user: CurrentUser, session: SessionDep, previous: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
            current: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    from app.utils.serialization import to_jsonable
    return to_jsonable(an.compare_months(session, user.id, previous, current))


@router.get("/balance", summary="Total balance across active accounts")
def balance(user: CurrentUser, session: SessionDep):
    return {"total_balance": float(an.total_balance(session, user.id)), "currency": user.currency}
