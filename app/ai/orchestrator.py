"""AI orchestrator: question -> tool selection -> tool execution -> explanation.

Facts always come from backend tools. With an LLM configured the model chooses tools and explains
results; without one (or when the provider fails) a deterministic rule router answers instead."""
import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.ai import memory, rules_router
from app.ai import provider as provider_mod
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.schemas import AskResult
from app.ai.tools import REGISTRY, all_specs
from app.core.exceptions import AIProviderError, AppError, ToolArgumentError
from app.core.metrics import AI_REQUESTS, AI_TOOL_CALLS
from app.db.models import Category

log = logging.getLogger(__name__)
MAX_STEPS = 5
MAX_TOOL_CALLS_PER_STEP = 4
_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


async def run_tool(session: Session, user_id: int, name: str, args: dict) -> dict:
    """Execute a tool defensively. Errors are returned as data so the model can recover."""
    tool = REGISTRY.get(name)
    if tool is None:
        AI_TOOL_CALLS.labels(name[:40], "unknown").inc()
        return {"error": f"Unknown tool '{name}'."}
    try:
        result = await run_in_threadpool(tool.run, session, user_id, args)
        AI_TOOL_CALLS.labels(name, "ok").inc()
        log.info("tool executed", extra={"tool": name})
        return result
    except ToolArgumentError as exc:
        AI_TOOL_CALLS.labels(name, "invalid_args").inc()
        return {"error": exc.message, "code": exc.code}
    except AppError as exc:
        AI_TOOL_CALLS.labels(name, "app_error").inc()
        return {"error": exc.message, "code": exc.code}
    except Exception:  # noqa: BLE001
        session.rollback()
        AI_TOOL_CALLS.labels(name, "error").inc()
        log.exception("tool crashed", extra={"tool": name})
        return {"error": "The tool failed unexpectedly."}


def _numbers_in(obj: Any, acc: list[Decimal]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float, Decimal)):
        acc.append(abs(Decimal(str(obj))))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers_in(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _numbers_in(v, acc)


def find_unsupported_numbers(answer: str, data: Any) -> list[str]:
    """Numbers in the LLM's prose that do not appear in any tool result (small tolerance for rounding)."""
    supported: list[Decimal] = []
    _numbers_in(data, supported)
    bad: list[str] = []
    for tok in _NUMBER.findall(answer):
        try:
            v = abs(Decimal(tok.replace(",", "")))
        except InvalidOperation:
            continue
        if v == v.to_integral_value() and (v <= 31 or 1900 <= v <= 2100):
            continue  # days, counts, years
        if not any(abs(s - v) <= max(Decimal("0.01"), s * Decimal("0.005")) for s in supported):
            bad.append(tok)
    return list(dict.fromkeys(bad))


def _pack(results: dict[str, Any]) -> dict:
    return next(iter(results.values())) if len(results) == 1 else results


async def _answer_with_rules(session: Session, user_id: int, question: str) -> tuple[str, list[str], dict]:
    names = [n for n in (await run_in_threadpool(
        lambda: session.execute(select(Category.name).where(Category.user_id == user_id)).scalars().all()))]
    steps = rules_router.plan(question, date.today(), names)
    used, results, parts = [], {}, []
    for name, args in steps:
        res = await run_tool(session, user_id, name, args)
        parts.append(rules_router.render(name, res))
        if "error" not in res:
            used.append(name)
            results[name] = res
    return "\n\n".join(parts), used, _pack(results) if results else {}


async def _answer_with_llm(session: Session, user_id: int, question: str, history: list[dict]):
    provider = provider_mod.get_provider()
    system = SYSTEM_PROMPT.format(today=date.today().isoformat())
    messages: list[dict] = [*history, {"role": "user", "content": question}]
    specs = all_specs()
    used: list[str] = []
    results: dict[str, Any] = {}
    final: str | None = None
    for _ in range(MAX_STEPS):
        resp = await provider.generate_with_tools(messages, specs, system=system)
        if not resp.tool_calls:
            final = resp.content
            break
        messages.append({"role": "assistant", "content": resp.content, "tool_calls": [
            {"id": c.id, "name": c.name, "arguments": c.arguments} for c in resp.tool_calls[:MAX_TOOL_CALLS_PER_STEP]]})
        for call in resp.tool_calls[:MAX_TOOL_CALLS_PER_STEP]:
            out = await run_tool(session, user_id, call.name, call.arguments)
            if "error" not in out:
                key = call.name if call.name not in results else f"{call.name}#{len(results)}"
                results[key] = out
                used.append(call.name)
            messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                             "content": json.dumps(out, default=str)})
    if not final:  # step budget exhausted: ask for a final answer without tools
        resp = await provider.generate(messages, system=system)
        final = resp.content
    if not final:
        raise AIProviderError("AI provider returned an empty answer.")
    return final.strip(), list(dict.fromkeys(used)), (_pack(results) if results else {})


async def ask(session: Session, user_id: int, question: str, conversation_id: int | None = None) -> AskResult:
    conv = await run_in_threadpool(memory.get_or_create, session, user_id, conversation_id, question)
    history = await run_in_threadpool(memory.history, session, conv.id)
    await run_in_threadpool(memory.add_message, session, conv.id, "user", question)

    source, unverified = "rules", []
    if provider_mod.get_provider() is not None:
        try:
            answer, used, data = await _answer_with_llm(session, user_id, question, history)
            source = "llm"
            unverified = find_unsupported_numbers(answer, data)
            AI_REQUESTS.labels("llm").inc()
        except AIProviderError as exc:
            log.warning("LLM failed, using rules router", extra={"error": exc.code})
            AI_REQUESTS.labels("provider_error_fallback").inc()
            answer, used, data = await _answer_with_rules(session, user_id, question)
            answer += "\n\n(The AI model is unavailable right now; this answer was generated from your data directly.)"
    else:
        answer, used, data = await _answer_with_rules(session, user_id, question)
        AI_REQUESTS.labels("rules").inc()

    await run_in_threadpool(memory.add_message, session, conv.id, "assistant", answer,
                            {"tools_used": used, "source": source})
    return AskResult(answer, used, data, source, conv.id, unverified)
