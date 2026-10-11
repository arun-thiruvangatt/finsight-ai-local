import re
from datetime import date, datetime, timedelta

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def month_str(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def parse_month(value: str) -> date:
    """'2026-10' -> date(2026, 10, 1)."""
    m = _MONTH_RE.match(value or "")
    if not m:
        raise ValueError("month must look like YYYY-MM")
    return date(int(m.group(1)), int(m.group(2)), 1)


def add_months(d: date, n: int) -> date:
    idx = d.year * 12 + (d.month - 1) + n
    return date(idx // 12, idx % 12 + 1, 1)


def month_bounds(month: str | date) -> tuple[date, date]:
    """Returns (first_day, first_day_of_next_month) -> half-open interval."""
    start = parse_month(month) if isinstance(month, str) else month.replace(day=1)
    return start, add_months(start, 1)


def previous_month(month: str) -> str:
    return month_str(add_months(parse_month(month), -1))


def week_bounds(d: date) -> tuple[date, date]:
    start = d - timedelta(days=d.weekday())
    return start, start + timedelta(days=7)


def days_in_range(start: date, end_exclusive: date) -> int:
    return (end_exclusive - start).days


_FORMATS_DAY_FIRST = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%d %B %Y"]
_FORMATS_MONTH_FIRST = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y"]


def parse_date_flexible(text: str, dayfirst: bool = True) -> date:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty date")
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", *(_FORMATS_DAY_FIRST + _FORMATS_MONTH_FIRST if dayfirst
                                          else _FORMATS_MONTH_FIRST + _FORMATS_DAY_FIRST)]:
        try:
            return datetime.strptime(raw[:19] if "T" in raw else raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError as exc:
        raise ValueError(f"unrecognised date: {raw!r}") from exc


def parse_month_mentions(text: str, today: date) -> list[str]:
    """Find months in free text: 'last month', 'this month', 'September', 'sep 2025', '2026-09'."""
    t = text.lower()
    found: list[tuple[int, str]] = []
    for m in re.finditer(r"\b(\d{4})-(0[1-9]|1[0-2])\b", t):
        found.append((m.start(), m.group(0)))
    for m in re.finditer(r"\b(" + "|".join(sorted(MONTH_NAMES, key=len, reverse=True)) + r")\b(?:\s+(\d{4}))?", t):
        num = MONTH_NAMES[m.group(1)]
        if m.group(2):
            year = int(m.group(2))
        else:  # no year -> most recent such month that is not in the future
            year = today.year if num <= today.month else today.year - 1
        found.append((m.start(), f"{year:04d}-{num:02d}"))
    cur = month_str(today)
    for phrase, value in (("last month", previous_month(cur)), ("previous month", previous_month(cur)),
                          ("this month", cur), ("current month", cur)):
        idx = t.find(phrase)
        if idx >= 0:
            found.append((idx, value))
    found.sort()
    out: list[str] = []
    for _, val in found:
        if val not in out:
            out.append(val)
    return out
