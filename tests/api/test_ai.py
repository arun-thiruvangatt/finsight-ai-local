"""Assistant tests. The LLM is replaced by a scripted fake provider; no network is used."""
from datetime import date

import pytest

from app.ai import provider as provider_mod
from app.ai.schemas import LLMResponse, ToolCall
from app.core.exceptions import AIProviderError
from app.utils.dates import month_str, previous_month
from tests.conftest import add_tx

LAST = previous_month(month_str(date.today()))


class FakeProvider:
    name, model = "fake", "fake-1"

    def __init__(self, script):
        self.script, self.calls = list(script), []

    async def generate(self, messages, **kw):
        return LLMResponse("fallback text")

    async def generate_structured(self, messages, schema, **kw):
        return {"results": []}

    async def generate_with_tools(self, messages, tools, **kw):
        self.calls.append(messages)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


@pytest.fixture
def use_provider(monkeypatch):
    def _install(script):
        fake = FakeProvider(script)
        monkeypatch.setattr(provider_mod, "get_provider", lambda: fake)
        return fake
    return _install


def _seed_food(client, auth, account):
    add_tx(client, auth, account["id"], "7840", "EXPENSE", f"{LAST}-10", "Swiggy")


def ask(client, auth, q):
    r = client.post("/api/v1/ai/ask", headers=auth, json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_rules_assistant_answers_from_database(client, auth, account):
    _seed_food(client, auth, account)
    out = ask(client, auth, "How much did I spend on food last month?")
    assert out["source"] == "rules" and out["tools_used"] == ["get_category_expenses"]
    assert "₹7,840" in out["answer"] and out["data"]["amount"] == 7840 and out["data"]["category"] == "Food"
    assert "not" in out["disclaimer"].lower()


def test_llm_tool_selection_and_explanation(client, auth, account, use_provider):
    _seed_food(client, auth, account)
    fake = use_provider([
        LLMResponse(None, [ToolCall("c1", "get_category_expenses", {"category": "Food", "month": LAST})]),
        LLMResponse("You spent ₹7,840 on Food last month."),
    ])
    out = ask(client, auth, "food spending last month?")
    assert out["source"] == "llm" and out["tools_used"] == ["get_category_expenses"]
    assert out["data"]["amount"] == 7840 and out["unverified_numbers"] == []
    tool_msg = [m for m in fake.calls[1] if m["role"] == "tool"][0]  # model received structured tool output
    assert '"amount": 7840' in tool_msg["content"]


def test_llm_invented_numbers_are_flagged(client, auth, account, use_provider):
    _seed_food(client, auth, account)
    use_provider([LLMResponse(None, [ToolCall("c1", "get_category_expenses", {"category": "Food", "month": LAST})]),
                  LLMResponse("You spent ₹9,999 on food.")])
    assert ask(client, auth, "food last month")["unverified_numbers"] == ["9,999"]


def test_invalid_tool_arguments_are_returned_to_model_not_executed(client, auth, account, use_provider):
    fake = use_provider([
        LLMResponse(None, [ToolCall("c1", "get_transactions", {"user_id": 2, "limit": 5})]),  # model tries to pick a user
        LLMResponse(None, [ToolCall("c2", "drop_database", {})]),                              # and an unknown tool
        LLMResponse("I could not fetch that."),
    ])
    out = ask(client, auth, "list transactions")
    assert out["tools_used"] == [] and out["source"] == "llm"
    errors = [m["content"] for call in fake.calls for m in call if m["role"] == "tool"]
    assert any("INVALID_TOOL_ARGUMENTS" in e for e in errors) and any("Unknown tool" in e for e in errors)


def test_provider_failure_falls_back_to_rules(client, auth, account, use_provider):
    _seed_food(client, auth, account)
    use_provider([AIProviderError("boom")])
    out = ask(client, auth, "How much did I spend on food last month?")
    assert out["source"] == "rules" and "₹7,840" in out["answer"] and "unavailable" in out["answer"]


def test_missing_data_is_reported_not_invented(client, auth):
    assert "no active budgets" in ask(client, auth, "Am I on track with my budget?")["answer"].lower()
    assert "No unusual" in ask(client, auth, "show me unusual transactions")["answer"]
    out = ask(client, auth, "How much did I spend on food last month?")
    assert out["data"]["amount"] == 0  # real zero from the DB
    unknown = ask(client, auth, "How much did I spend on spaceships")
    assert unknown["data"]["expenses"] == 0  # unknown topic -> generic real summary, nothing invented


def test_question_validation_and_conversation_memory(client, auth, account):
    assert client.post("/api/v1/ai/ask", headers=auth, json={"question": "x"}).status_code == 422
    first = ask(client, auth, "How much did I spend this month?")
    second = client.post("/api/v1/ai/ask", headers=auth, json={"question": "and my budget?", "conversation_id": first["conversation_id"]})
    assert second.json()["conversation_id"] == first["conversation_id"]
    msgs = client.get(f"/api/v1/ai/conversations/{first['conversation_id']}/messages", headers=auth).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
