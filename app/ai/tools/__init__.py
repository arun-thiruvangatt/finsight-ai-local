"""Safe, parameterised backend tools exposed to the assistant. The model can only pick a tool and
supply validated arguments - it never writes SQL and never supplies the user id."""
from app.ai.tools import analytics, anomalies, budgets, documents, goals, recurring, transactions  # noqa: F401
from app.ai.tools.base import REGISTRY, Tool

__all__ = ["REGISTRY", "Tool", "get_tool", "all_specs"]


def get_tool(name: str) -> Tool | None:
    return REGISTRY.get(name)


def all_specs():
    return [t.spec() for t in REGISTRY.values()]
