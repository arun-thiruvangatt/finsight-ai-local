from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = ""


@dataclass
class AskResult:
    answer: str
    tools_used: list[str]
    data: dict[str, Any]
    source: str  # "llm" | "rules"
    conversation_id: int
    unverified_numbers: list[str] = field(default_factory=list)
