"""Money helpers. All financial maths uses Decimal - never float."""
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")
_CURRENCY_NOISE = re.compile(r"(?i)(₹|\$|€|£|rs\.?|inr|usd|eur|gbp|,|\s)")


def D(value: object) -> Decimal:
    """Convert to Decimal safely (floats go through str to avoid binary artefacts)."""
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    try:
        return Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"not a valid number: {value!r}") from exc


def quantize(value: object) -> Decimal:
    return D(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_money(text: str) -> Decimal:
    """Parse '₹1,234.50', '(500.00)', '-12', '1 234' ... Parentheses mean negative."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty amount")
    negative = raw.startswith("(") and raw.endswith(")")
    cleaned = _CURRENCY_NOISE.sub("", raw).strip("()")
    if cleaned.endswith("-"):  # trailing minus
        cleaned, negative = cleaned[:-1], True
    value = D(cleaned)
    return -abs(value) if negative else value


def safe_div(numerator: object, denominator: object) -> Decimal:
    den = D(denominator)
    return Decimal("0") if den == 0 else D(numerator) / den


def percentage(part: object, whole: object) -> Decimal:
    return quantize(safe_div(part, whole) * 100)


def pct_change(old: object, new: object) -> Decimal | None:
    """Percentage change old -> new; None when old is zero (undefined)."""
    if D(old) == 0:
        return None
    return quantize((D(new) - D(old)) / D(old) * 100)


def format_inr(value: object, symbol: str = "₹") -> str:
    """Indian digit grouping: 1234567.5 -> ₹12,34,567.50 ; whole numbers drop the decimals."""
    q = quantize(value)
    sign = "-" if q < 0 else ""
    whole, _, frac = f"{abs(q):.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join([*parts, tail])
    return f"{sign}{symbol}{whole}" + ("" if frac == "00" else f".{frac}")
