from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_jsonable(obj: Any) -> Any:
    """Recursively convert Decimal/date to JSON types. Decimals only become numbers at the
    presentation boundary - all arithmetic has already happened in Decimal."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return to_jsonable(obj.model_dump())
    return obj
