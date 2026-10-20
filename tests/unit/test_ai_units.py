from datetime import date

import pytest

from app.ai import rag, rules_router
from app.ai.embeddings import HashingEmbedder
from app.ai.orchestrator import find_unsupported_numbers
from app.ai.tools import REGISTRY, all_specs
from app.core.exceptions import ToolArgumentError

TODAY = date(2026, 10, 9)
CATS = ["Food", "Transport", "Shopping", "Groceries"]


def test_registry_has_all_required_tools():
    required = {"get_transactions", "get_transaction", "get_monthly_summary", "get_category_expenses",
                "get_category_trends", "get_income_summary", "get_cashflow", "compare_months", "get_budget_status",
                "get_goal_status", "get_recurring_expenses", "get_anomalies", "get_top_merchants"}
    assert required <= set(REGISTRY)
    for spec in all_specs():
        assert spec.parameters["type"] == "object"
        assert "user_id" not in spec.parameters.get("properties", {})  # model can never choose the user


@pytest.mark.parametrize("args", [{"user_id": 2}, {"limit": 9999}, {"transaction_type": "DROP TABLE"}, {"from_date": "x"}])
def test_tool_rejects_invalid_arguments_before_touching_db(args):
    with pytest.raises(ToolArgumentError):
        REGISTRY["get_transactions"].run(None, 1, args)  # session is never used


def test_tool_rejects_bad_month():
    with pytest.raises(ToolArgumentError):
        REGISTRY["get_monthly_summary"].run(None, 1, {"month": "2026-13"})


@pytest.mark.parametrize("question,tool,args", [
    ("How much did I spend on food last month?", "get_category_expenses", {"category": "Food", "month": "2026-09"}),
    ("Why did my spending increase this month?", "compare_months", {"current_month": "2026-10", "previous_month": "2026-09"}),
    ("Compare my spending in September and October", "compare_months", {"previous_month": "2026-09", "current_month": "2026-10"}),
    ("What are my largest recurring expenses?", "get_recurring_expenses", {}),
    ("Show me unusual transactions.", "get_anomalies", {}),
    ("Am I on track with my monthly budget?", "get_budget_status", {}),
    ("How much can I safely allocate toward my goal?", "get_goal_status", {}),
    ("What did I earn in September", "get_income_summary", {"month": "2026-09"}),
])
def test_rules_router_plans(question, tool, args):
    assert rules_router.plan(question, TODAY, CATS) == [(tool, args)]


def test_rules_router_falls_back_to_document_search():
    assert rules_router.plan("what does my insurance cover", TODAY, CATS)[0][0] == "search_documents"


def test_unsupported_number_detection():
    data = {"amount": 7840, "previous": 6860.0, "pct": 14.29}
    assert find_unsupported_numbers("You spent ₹7,840, up 14.3% from ₹6,860.", data) == []
    assert find_unsupported_numbers("You spent ₹9,999 in 2026 over 3 months.", data) == ["9,999"]


def test_chunking_and_hashing_embedder():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 120 for i in range(10))
    chunks = rag.chunk_text(rag.clean_text(text))
    assert len(chunks) > 3 and all(len(c) <= 1100 for c in chunks)
    assert rag.chunk_text("") == []

    import asyncio
    emb = HashingEmbedder(384)
    a, b, c = asyncio.run(emb.embed(["health insurance premium renewal", "insurance premium for health cover",
                                      "rent agreement lease hike"]))
    dot = lambda x, y: sum(p * q for p, q in zip(x, y, strict=True))  # noqa: E731
    assert len(a) == 384 and abs(dot(a, a) - 1) < 1e-6
    assert dot(a, b) > dot(a, c)


def test_extract_text_ocr_only_scanned_pdf_pages(monkeypatch, tmp_path):
    import sys
    from types import ModuleType, SimpleNamespace

    import pypdf

    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    monkeypatch.setattr(
        pypdf, "PdfReader", lambda _: SimpleNamespace(pages=[Page("searchable text"), Page(None), Page(" ")])
    )
    converted_pages = []
    pdf2image = ModuleType("pdf2image")

    def convert_from_path(pdf_path, *, dpi, first_page, last_page, timeout):
        converted_pages.append(first_page)
        return [first_page]

    pdf2image.convert_from_path = convert_from_path
    pytesseract = ModuleType("pytesseract")
    pytesseract.image_to_string = lambda image, *, lang, timeout: f"recognized page {image}"
    pytesseract.TesseractNotFoundError = RuntimeError
    monkeypatch.setitem(sys.modules, "pdf2image", pdf2image)
    monkeypatch.setitem(sys.modules, "pytesseract", pytesseract)

    pdf_path = tmp_path / "statement.pdf"
    pdf_path.touch()
    assert rag.extract_text(pdf_path) == "searchable text\n\nrecognized page 2\n\nrecognized page 3"
    assert converted_pages == [2, 3]


def test_extract_text_skips_ocr_for_searchable_pdf(monkeypatch, tmp_path):
    from types import SimpleNamespace

    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "statement text")]))
    pdf_path = tmp_path / "statement.pdf"
    pdf_path.touch()
    assert rag.extract_text(pdf_path) == "statement text"
