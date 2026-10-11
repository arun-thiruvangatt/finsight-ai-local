"""Bank-statement CSV parsing: header aliasing, custom mapping, debit/credit columns."""
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.core.exceptions import AppError
from app.utils.dates import parse_date_flexible
from app.utils.money import ZERO, parse_money, quantize

ALIASES: dict[str, list[str]] = {
    "date": ["date", "transaction date", "txn date", "value date", "posting date", "tran date", "trans date"],
    "description": ["description", "narration", "details", "particulars", "remarks", "transaction details",
                    "transaction description"],
    "amount": ["amount", "transaction amount", "amt"],
    "debit": ["debit", "withdrawal", "withdrawal amt", "withdrawals", "debit amount", "dr"],
    "credit": ["credit", "deposit", "deposit amt", "deposits", "credit amount", "cr"],
    "type": ["type", "transaction type", "dr/cr", "cr/dr", "txn type"],
    "reference": ["reference", "ref", "ref no", "reference number", "utr", "cheque no", "chq/ref no", "ref no."],
    "merchant": ["merchant", "payee", "counterparty"],
}
CANONICAL = tuple(ALIASES)

_EXPENSE_WORDS = {"debit", "dr", "d", "withdrawal", "expense", "out", "purchase", "sale"}
_INCOME_WORDS = {"credit", "cr", "c", "deposit", "income", "in", "refund"}
_STOP_TOKENS = {"upi", "pos", "imps", "neft", "rtgs", "ach", "ecs", "atm", "payment", "pay", "txn", "to", "from",
                "debit", "credit", "card", "purchase", "ref", "bank", "transfer"}


@dataclass
class ParsedRow:
    date: date
    amount: Decimal  # always positive
    transaction_type: str
    merchant: str | None
    description: str | None
    reference: str | None


def read_headers(path: str | Path) -> list[str]:
    try:
        df = pd.read_csv(path, nrows=0, dtype=str, encoding="utf-8-sig", sep=None, engine="python")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise AppError("File is not a readable CSV.", code="INVALID_CSV") from exc
    return [str(c).strip() for c in df.columns]


def resolve_mapping(headers: list[str], override: dict[str, str] | None = None) -> dict[str, str]:
    """canonical field -> actual header. `override` lets the user choose columns explicitly."""
    by_lower = {h.strip().lower(): h for h in headers}
    mapping: dict[str, str] = {}
    for field, wanted in (override or {}).items():
        if field not in CANONICAL:
            raise AppError(f"Unknown mapping field '{field}'.", code="INVALID_MAPPING")
        if wanted.strip().lower() not in by_lower:
            raise AppError(f"Mapped column '{wanted}' not found in file.", code="INVALID_MAPPING")
        mapping[field] = by_lower[wanted.strip().lower()]
    for field, names in ALIASES.items():
        if field in mapping:
            continue
        for n in names:
            if n in by_lower:
                mapping[field] = by_lower[n]
                break
    if "date" not in mapping:
        raise AppError("Could not find a date column. Provide column_mapping.", code="INVALID_MAPPING")
    if "amount" not in mapping and not ("debit" in mapping or "credit" in mapping):
        raise AppError("Could not find an amount (or debit/credit) column. Provide column_mapping.",
                       code="INVALID_MAPPING")
    return mapping


def iter_csv_chunks(path: str | Path, chunksize: int = 1000) -> Iterator[list[tuple[int, dict[str, str]]]]:
    """Yield lists of (row_number, row_dict). Row numbers match the spreadsheet (header = 1)."""
    reader = pd.read_csv(path, dtype=str, keep_default_na=False, chunksize=chunksize, encoding="utf-8-sig",
                         sep=None, engine="python", skipinitialspace=True)
    for chunk in reader:
        chunk.columns = [str(c).strip() for c in chunk.columns]
        records = chunk.to_dict("records")
        yield [(int(idx) + 2, {k: (v or "").strip() for k, v in rec.items()})
               for idx, rec in zip(chunk.index, records, strict=True)]


def count_rows(path: str | Path) -> int:
    return sum(len(c) for c in iter_csv_chunks(path, 5000))


def normalize_merchant(description: str | None) -> str | None:
    if not description:
        return None
    parts = re.split(r"[/|*@]+|\s-\s|^-", description)
    candidates = []
    for p in parts:
        token = re.sub(r"\d{4,}", " ", p)
        token = re.sub(r"[^A-Za-z&' .]", " ", token)
        token = re.sub(r"\s+", " ", token).strip()
        if len(token) >= 3 and token.lower() not in _STOP_TOKENS:
            candidates.append(token)
    chosen = candidates[0] if candidates else re.sub(r"\s+", " ", description).strip()
    return chosen.title()[:60] or None


def _type_from_word(word: str) -> str | None:
    w = word.strip().lower()
    if w in _EXPENSE_WORDS:
        return "EXPENSE"
    if w in _INCOME_WORDS:
        return "INCOME"
    if w.startswith("transfer"):
        return "TRANSFER"
    return None


def parse_row(row: dict[str, str], mapping: dict[str, str], dayfirst: bool = True) -> ParsedRow:
    tx_date = parse_date_flexible(row.get(mapping["date"], ""), dayfirst=dayfirst)
    description = row.get(mapping.get("description", ""), "") or None
    reference = row.get(mapping.get("reference", ""), "") or None
    explicit_type = _type_from_word(row.get(mapping["type"], "")) if "type" in mapping else None

    amount: Decimal
    ttype: str | None
    if "amount" in mapping and row.get(mapping["amount"], "").strip():
        signed = parse_money(row[mapping["amount"]])
        amount = abs(signed)
        ttype = explicit_type or ("EXPENSE" if signed < 0 else "INCOME")
    else:
        debit = parse_money(row.get(mapping.get("debit", ""), "") or "0")
        credit = parse_money(row.get(mapping.get("credit", ""), "") or "0")
        if debit and credit:
            raise ValueError("both debit and credit set")
        amount, ttype = (abs(debit), "EXPENSE") if debit else (abs(credit), explicit_type or "INCOME")
    amount = quantize(amount)
    if amount == ZERO:
        raise ValueError("amount is zero")
    merchant = row.get(mapping.get("merchant", ""), "") or normalize_merchant(description)
    return ParsedRow(tx_date, amount, ttype or "EXPENSE", merchant, description, reference)
