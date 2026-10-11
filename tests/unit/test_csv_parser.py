from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.utils.csv_parser import normalize_merchant, parse_row, resolve_mapping


def test_default_mapping_and_aliases():
    m = resolve_mapping(["Txn Date", "Narration", "Withdrawal Amt", "Deposit Amt", "Chq/Ref No"])
    assert m == {"date": "Txn Date", "description": "Narration", "debit": "Withdrawal Amt", "credit": "Deposit Amt",
                 "reference": "Chq/Ref No"}


def test_custom_mapping_and_errors():
    m = resolve_mapping(["When", "What", "How much"], {"date": "when", "description": "what", "amount": "how much"})
    assert m["amount"] == "How much"
    with pytest.raises(AppError):
        resolve_mapping(["Description", "Amount"])  # no date
    with pytest.raises(AppError):
        resolve_mapping(["Date", "Description"])  # no amount
    with pytest.raises(AppError):
        resolve_mapping(["Date", "Amount"], {"date": "Missing"})


def test_parse_row_variants():
    m = {"date": "Date", "description": "Description", "amount": "Amount", "type": "Type", "reference": "Reference"}
    r = parse_row({"Date": "2026-09-03", "Description": "UPI/SWIGGY/123456789/Pay", "Amount": "250.50",
                   "Type": "Debit", "Reference": "R1"}, m)
    assert (r.date, r.amount, r.transaction_type, r.merchant) == (date(2026, 9, 3), Decimal("250.50"), "EXPENSE", "Swiggy")
    r = parse_row({"Date": "03/09/2026", "Description": "Salary", "Amount": "24,000", "Type": "", "Reference": ""}, m)
    assert r.transaction_type == "INCOME" and r.amount == Decimal("24000.00")
    r = parse_row({"Date": "2026-09-03", "Description": "x shop", "Amount": "-80", "Type": "", "Reference": ""}, m)
    assert r.transaction_type == "EXPENSE" and r.amount == Decimal("80.00")


def test_parse_row_debit_credit_columns_and_bad_rows():
    m = {"date": "D", "description": "N", "debit": "Dr", "credit": "Cr"}
    assert parse_row({"D": "2026-09-01", "N": "ATM", "Dr": "500", "Cr": ""}, m).transaction_type == "EXPENSE"
    assert parse_row({"D": "2026-09-01", "N": "Pay", "Dr": "", "Cr": "900"}, m).transaction_type == "INCOME"
    for bad in ({"D": "2026-09-01", "N": "x", "Dr": "0", "Cr": "0"}, {"D": "nope", "N": "x", "Dr": "5", "Cr": ""},
                {"D": "2026-09-01", "N": "x", "Dr": "5", "Cr": "5"}):
        with pytest.raises(ValueError):
            parse_row(bad, m)


def test_normalize_merchant():
    assert normalize_merchant("UPI/SWIGGY/1234567890/Payment") == "Swiggy"
    assert normalize_merchant("POS 4521 STARBUCKS COFFEE") == "Pos Starbucks Coffee"
    assert normalize_merchant(None) is None
