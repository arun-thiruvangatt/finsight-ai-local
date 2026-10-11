"""LLM provider abstraction. The rest of the codebase depends on `LLMProvider` only.

Messages are plain dicts:
  {"role": "user"|"assistant", "content": str}
  {"role": "assistant", "content": str|None, "tool_calls": [{"id", "name", "arguments"}]}
  {"role": "tool", "tool_call_id": str, "name": str, "content": str}
"""
import json
import logging
import time
from functools import lru_cache
from typing import Any, Protocol

import httpx

from app.ai.schemas import LLMResponse, ToolCall, ToolSpec
from app.core.config import get_settings
from app.core.exceptions import AIProviderError
from app.core.metrics import AI_LATENCY

log = logging.getLogger(__name__)
Messages = list[dict[str, Any]]


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(self, messages: Messages, *, system: str | None = None, temperature: float = 0.2,
                       max_tokens: int = 800) -> LLMResponse: ...

    async def generate_structured(self, messages: Messages, schema: dict, *, system: str | None = None) -> dict: ...

    async def generate_with_tools(self, messages: Messages, tools: list[ToolSpec], *, system: str | None = None,
                                  max_tokens: int = 1000) -> LLMResponse: ...


class _HTTPProvider:
    name = "http"

    def __init__(self, api_key: str, model: str, base_url: str, timeout: float = 60.0):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url.rstrip("/"), timeout

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    async def _post(self, path: str, payload: dict, op: str) -> dict:
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}{path}", json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise AIProviderError(f"AI provider returned HTTP {exc.response.status_code}.",
                                  details=exc.response.text[:300]) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise AIProviderError("AI provider request failed.") from exc
        finally:
            elapsed = time.perf_counter() - started
            AI_LATENCY.labels(op).observe(elapsed)
            log.info("llm call", extra={"model": self.model, "latency_ms": round(elapsed * 1000), "tool": op})
        return data


class OpenAICompatProvider(_HTTPProvider):
    """Works with OpenAI and any OpenAI-compatible server (Azure proxies, vLLM, Ollama, ...)."""
    name = "openai"

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    @staticmethod
    def _convert(messages: Messages, system: str | None) -> list[dict]:
        out: list[dict] = [{"role": "system", "content": system}] if system else []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append({"role": "assistant", "content": m.get("content"), "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])}}
                    for tc in m["tool_calls"]]})
            elif m["role"] == "tool":
                out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return out

    @staticmethod
    def _parse(data: dict, model: str) -> LLMResponse:
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("Unexpected response from AI provider.") from exc
        calls = []
        for tc in msg.get("tool_calls") or []:
            raw = tc["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
            except json.JSONDecodeError:
                args = {"__invalid_json__": raw[:200]}
            calls.append(ToolCall(tc["id"], tc["function"]["name"], args if isinstance(args, dict) else {}))
        usage = data.get("usage") or {}
        return LLMResponse(msg.get("content"), calls, {"total_tokens": usage.get("total_tokens", 0)}, model)

    async def generate(self, messages, *, system=None, temperature=0.2, max_tokens=800) -> LLMResponse:
        data = await self._post("/chat/completions", {
            "model": self.model, "messages": self._convert(messages, system),
            "temperature": temperature, "max_tokens": max_tokens}, "generate")
        return self._parse(data, self.model)

    async def generate_structured(self, messages, schema, *, system=None) -> dict:
        payload = {"model": self.model, "messages": self._convert(messages, system), "temperature": 0,
                   "response_format": {"type": "json_schema",
                                       "json_schema": {"name": "output", "schema": schema, "strict": False}}}
        try:
            data = await self._post("/chat/completions", payload, "structured")
        except AIProviderError:
            # Some compatible servers lack json_schema support: retry in JSON mode with the schema in the prompt.
            sys2 = (system or "") + "\nRespond with JSON only matching this JSON schema: " + json.dumps(schema)
            payload = {"model": self.model, "messages": self._convert(messages, sys2), "temperature": 0,
                       "response_format": {"type": "json_object"}}
            data = await self._post("/chat/completions", payload, "structured")
        content = self._parse(data, self.model).content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIProviderError("AI provider returned invalid JSON.") from exc

    async def generate_with_tools(self, messages, tools, *, system=None, max_tokens=1000) -> LLMResponse:
        data = await self._post("/chat/completions", {
            "model": self.model, "messages": self._convert(messages, system), "temperature": 0.1,
            "max_tokens": max_tokens, "tool_choice": "auto",
            "tools": [{"type": "function", "function": {"name": t.name, "description": t.description,
                                                         "parameters": t.parameters}} for t in tools]}, "tools")
        return self._parse(data, self.model)


class AnthropicProvider(_HTTPProvider):
    name = "anthropic"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}

    @staticmethod
    def _convert(messages: Messages) -> list[dict]:
        out: list[dict] = []
        for m in messages:
            if m["role"] == "assistant":
                blocks: list[dict] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls") or []:
                    blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["arguments"]})
                out.append({"role": "assistant", "content": blocks or m.get("content") or ""})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                last = out[-1] if out else None
                if last and last["role"] == "user" and isinstance(last["content"], list) \
                        and all(b.get("type") == "tool_result" for b in last["content"]):
                    last["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
            else:
                out.append({"role": "user", "content": m["content"]})
        return out

    @staticmethod
    def _parse(data: dict, model: str) -> LLMResponse:
        text, calls = [], []
        for b in data.get("content") or []:
            if b.get("type") == "text":
                text.append(b["text"])
            elif b.get("type") == "tool_use":
                calls.append(ToolCall(b["id"], b["name"], b.get("input") or {}))
        u = data.get("usage") or {}
        return LLMResponse("".join(text) or None, calls,
                           {"total_tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0)}, model)

    async def _call(self, messages, system, op, max_tokens, **extra) -> dict:
        payload = {"model": self.model, "max_tokens": max_tokens, "messages": self._convert(messages), **extra}
        if system:
            payload["system"] = system
        return await self._post("/v1/messages", payload, op)

    async def generate(self, messages, *, system=None, temperature=0.2, max_tokens=800) -> LLMResponse:
        return self._parse(await self._call(messages, system, "generate", max_tokens, temperature=temperature), self.model)

    async def generate_structured(self, messages, schema, *, system=None) -> dict:
        tool = {"name": "emit", "description": "Return the structured result.", "input_schema": schema}
        data = await self._call(messages, system, "structured", 1500, tools=[tool],
                                tool_choice={"type": "tool", "name": "emit"}, temperature=0)
        calls = self._parse(data, self.model).tool_calls
        if not calls:
            raise AIProviderError("AI provider returned no structured output.")
        return calls[0].arguments

    async def generate_with_tools(self, messages, tools, *, system=None, max_tokens=1000) -> LLMResponse:
        specs = [{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools]
        return self._parse(await self._call(messages, system, "tools", max_tokens, tools=specs, temperature=0.1),
                           self.model)


@lru_cache
def get_provider() -> LLMProvider | None:
    """Returns the configured provider, or None => the app runs on its deterministic rule router."""
    s = get_settings()
    name = s.LLM_PROVIDER.strip().lower()
    if not name or not s.LLM_MODEL:
        return None
    if name == "anthropic":
        if not s.LLM_API_KEY:
            return None
        return AnthropicProvider(s.LLM_API_KEY, s.LLM_MODEL, s.LLM_BASE_URL or "https://api.anthropic.com")
    if not s.LLM_API_KEY and not s.LLM_BASE_URL:
        return None
    return OpenAICompatProvider(s.LLM_API_KEY, s.LLM_MODEL, s.LLM_BASE_URL or "https://api.openai.com/v1")
