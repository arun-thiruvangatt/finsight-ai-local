from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlmodel import Session

from app.ai.schemas import ToolSpec
from app.core.exceptions import ToolArgumentError
from app.utils.dates import month_bounds, month_str
from app.utils.serialization import to_jsonable

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class ToolArgs(BaseModel):
    """Base for tool argument models. extra='forbid' means a model can never smuggle in user_id etc."""
    model_config = ConfigDict(extra="forbid")


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[ToolArgs]
    handler: Callable[[Session, int, Any], Any]

    def spec(self) -> ToolSpec:
        schema = self.args_model.model_json_schema()
        schema.pop("title", None)
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
        return ToolSpec(self.name, self.description, schema)

    def run(self, session: Session, user_id: int, raw_args: dict | None) -> Any:
        """user_id comes from the authenticated request context, never from model output."""
        try:
            args = self.args_model.model_validate(raw_args or {})
        except ValidationError as exc:
            msgs = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
            raise ToolArgumentError(f"Invalid arguments for {self.name}: {msgs}") from exc
        return to_jsonable(self.handler(session, user_id, args))


REGISTRY: dict[str, Tool] = {}


def register(name: str, description: str, args_model: type[ToolArgs]):
    def deco(fn: Callable[[Session, int, Any], Any]):
        REGISTRY[name] = Tool(name, description, args_model, fn)
        return fn
    return deco


def resolve_range(month: str | None, from_date: date | None, to_date: date | None,
                  today: date | None = None) -> tuple[date, date, str]:
    """Returns (start, end_exclusive, label). Explicit dates win over month; default = current month."""
    today = today or date.today()
    if from_date or to_date:
        start = from_date or (to_date - timedelta(days=30))
        end_incl = to_date or today
        if end_incl < start:
            raise ToolArgumentError("to_date must not be before from_date.")
        return start, end_incl + timedelta(days=1), f"{start} to {end_incl}"
    m = month or month_str(today)
    start, end = month_bounds(m)
    return start, end, m
