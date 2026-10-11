from datetime import date, timedelta
from decimal import Decimal

from app.services.anomaly_service import Baseline, evaluate
from app.services.budget_service import build_warnings, project_spending
from app.services.recurring_service import analyze_series, classify_interval


def test_projection_is_linear_run_rate():
    # 3000 spent in the first 10 of 31 days -> 9300 projected
    assert project_spending(Decimal("3000"), date(2026, 10, 1), date(2026, 11, 1), date(2026, 10, 10)) == Decimal("9300.00")
    # window already over -> actual
    assert project_spending(Decimal("500"), date(2026, 9, 1), date(2026, 10, 1), date(2026, 10, 5)) == Decimal("500.00")
    # window not started -> zero
    assert project_spending(Decimal("0"), date(2026, 11, 1), date(2026, 12, 1), date(2026, 10, 5)) == Decimal("0.00")


def test_budget_warnings():
    assert build_warnings(Decimal("1000"), Decimal("500"), Decimal("600"), Decimal("80")) == []
    over = build_warnings(Decimal("1000"), Decimal("1200"), Decimal("1500"), Decimal("80"))
    assert over and "exceeded" in over[0]
    near = build_warnings(Decimal("1000"), Decimal("850"), Decimal("900"), Decimal("80"))
    assert "85" in near[0]
    pace = build_warnings(Decimal("1000"), Decimal("500"), Decimal("1400"), Decimal("80"))
    assert "Estimate" in pace[0]


def test_anomaly_evaluate():
    base = Baseline(mean=Decimal("500"), std=Decimal("100"), n=20, label="shopping")
    hit = evaluate(Decimal("1500"), base)
    assert hit and hit.score > 0.5 and "significantly higher" in hit.reason
    assert evaluate(Decimal("600"), base) is None
    assert evaluate(Decimal("5000"), Baseline(Decimal("500"), Decimal("100"), 3, "x")) is None  # too little history
    # fixed bill with zero variance: tiny wobble is NOT flagged, big jump is
    fixed = Baseline(Decimal("699"), Decimal("0"), 12, "internet")
    assert evaluate(Decimal("720"), fixed) is None
    assert evaluate(Decimal("1500"), fixed) is not None


def test_recurring_monthly_detected():
    ds = [date(2026, m, 10) for m in range(1, 7)]
    p = analyze_series(ds, [Decimal("649")] * 6)
    assert p and p["frequency"] == "monthly" and p["confidence"] >= 0.9
    assert p["next_expected"] == date(2026, 7, 10)


def test_recurring_weekly_and_yearly_and_noise():
    wk = [date(2026, 9, 1) + timedelta(days=7 * i) for i in range(5)]
    assert analyze_series(wk, [Decimal("100")] * 5)["frequency"] == "weekly"
    yr = [date(2024, 3, 5), date(2025, 3, 5)]
    assert analyze_series(yr, [Decimal("12000")] * 2)["frequency"] == "yearly"
    messy = [date(2026, 1, 1), date(2026, 1, 3), date(2026, 2, 20), date(2026, 2, 22)]
    assert analyze_series(messy, [Decimal("100")] * 4) is None
    assert classify_interval(15) is None
