from decimal import Decimal

import pytest

from app.utils.money import D, format_inr, parse_money, pct_change, percentage, quantize


def test_decimal_avoids_float_error():
    assert D("0.1") + D("0.2") == D("0.3")
    assert sum([D("0.01")] * 100) == D("1.00")
    assert D(0.1) == Decimal("0.1")  # floats go through str


@pytest.mark.parametrize("raw,expected", [
    ("₹1,234.50", "1234.50"), ("(500.00)", "-500.00"), ("-12", "-12"), ("Rs. 10,000.99", "10000.99"),
    ("100.10", "100.10"), ("0.01", "0.01"), ("250-", "-250"),
])
def test_parse_money(raw, expected):
    assert parse_money(raw) == Decimal(expected)


def test_parse_money_rejects_garbage():
    with pytest.raises(ValueError):
        parse_money("abc")
    with pytest.raises(ValueError):
        parse_money("")


def test_quantize_rounds_half_up():
    assert quantize("0.005") == Decimal("0.01")
    assert quantize("10000.994") == Decimal("10000.99")


def test_percentage_and_change():
    assert percentage(5500, 24000) == Decimal("22.92")
    assert percentage(1, 0) == Decimal("0.00")
    assert pct_change(6860, 7840) == Decimal("14.29")
    assert pct_change(0, 10) is None


def test_format_inr_indian_grouping():
    assert format_inr(7840) == "₹7,840"
    assert format_inr(1234567.5) == "₹12,34,567.50"
    assert format_inr(-999) == "-₹999"
    assert format_inr("100.10") == "₹100.10"
