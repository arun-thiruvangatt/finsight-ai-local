from datetime import date

import pytest

from app.core.exceptions import AppError
from app.utils.dates import add_months, month_bounds, parse_date_flexible, parse_month, parse_month_mentions, previous_month
from app.utils.validators import safe_filename, validate_currency, validate_timezone, validate_upload


def test_month_helpers():
    assert parse_month("2026-10") == date(2026, 10, 1)
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2027, 1, 1))
    assert previous_month("2026-01") == "2025-12"
    assert add_months(date(2026, 1, 1), -13) == date(2024, 12, 1)
    with pytest.raises(ValueError):
        parse_month("2026-13")


def test_parse_dates():
    assert parse_date_flexible("2026-09-03") == date(2026, 9, 3)
    assert parse_date_flexible("03/09/2026") == date(2026, 9, 3)
    assert parse_date_flexible("03/09/2026", dayfirst=False) == date(2026, 3, 9)
    assert parse_date_flexible("03 Sep 2026") == date(2026, 9, 3)
    assert parse_date_flexible("29-Jun-17") == date(2017, 6, 29)
    assert parse_date_flexible("5-Jul-17") == date(2017, 7, 5)
    with pytest.raises(ValueError):
        parse_date_flexible("not a date")


def test_month_mentions():
    today = date(2026, 10, 9)
    assert parse_month_mentions("food last month", today) == ["2026-09"]
    assert parse_month_mentions("compare September and October", today) == ["2026-09", "2026-10"]
    assert parse_month_mentions("spend in march 2025", today) == ["2025-03"]
    assert parse_month_mentions("anything", today) == []


def test_validators():
    assert validate_currency("inr") == "INR"
    with pytest.raises(ValueError):
        validate_currency("RUPEE")
    assert validate_timezone("Asia/Kolkata") == "Asia/Kolkata"
    with pytest.raises(ValueError):
        validate_timezone("Mars/Base")
    assert safe_filename("../../etc/passwd") == "passwd"
    assert safe_filename("my file (1).csv") == "my_file__1_.csv"


def test_validate_upload():
    assert validate_upload("a.csv", 10, {".csv"}, 100) == ".csv"
    for name, size in (("a.exe", 10), ("a.csv", 0), ("a.csv", 101)):
        with pytest.raises(AppError):
            validate_upload(name, size, {".csv"}, 100)
