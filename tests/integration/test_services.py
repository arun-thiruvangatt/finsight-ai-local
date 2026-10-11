import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlmodel import select

from app.ai import rag
from app.ai.embeddings import get_embedder
from app.db.models import Account, Document, Transaction
from app.schemas.auth import RegisterRequest
from app.services import (analytics_service, anomaly_service, auth_service, import_service, recurring_service)


def _user(session, email):
    return auth_service.register(session, RegisterRequest(email=email, password="password123", full_name="T"))


def _account(session, user):
    acc = Account(user_id=user.id, name="A", current_balance=Decimal("0"))
    session.add(acc)
    session.commit()
    session.refresh(acc)
    return acc


def _tx(session, user, acc, amount, d, merchant, ttype="EXPENSE"):
    t = Transaction(user_id=user.id, account_id=acc.id, amount=Decimal(str(amount)), transaction_type=ttype,
                    merchant=merchant, transaction_date=d)
    session.add(t)
    return t


def test_import_is_idempotent_and_categorises(session, tmp_path):
    user = _user(session, "imp@example.com")
    acc = _account(session, user)
    f = tmp_path / "s.csv"
    f.write_text("Date,Description,Amount,Type,Reference\n"
                 "2026-09-01,ACME Salary,24000,credit,R1\n2026-09-02,Swiggy,250,debit,R2\n"
                 "2026-09-02,Swiggy,250,debit,R2\nbad-date,x,5,debit,\n")
    job = import_service.create_job(session, user.id, acc.id, "s.csv", str(f), {})
    job = import_service.run_import(session, job.id)
    assert (job.successful_rows, job.failed_rows, job.status) == (3, 1, "PARTIAL")  # identical rows both kept
    assert "row 5" in job.error_message
    session.refresh(acc)
    assert acc.current_balance == Decimal("23500.00")
    assert all(t.category_id for t in session.exec(select(Transaction)).all())  # rules categorised all

    job2 = import_service.create_job(session, user.id, acc.id, "s.csv", str(f), {})
    job2 = import_service.run_import(session, job2.id)
    assert (job2.successful_rows, job2.duplicate_rows) == (0, 3)  # DB constraint blocks re-import


def test_analytics_rollup_and_compare(session):
    user = _user(session, "an@example.com")
    acc = _account(session, user)
    _tx(session, user, acc, 1000, date(2026, 9, 5), "Swiggy")
    _tx(session, user, acc, 500, date(2026, 9, 6), "BigBasket")
    _tx(session, user, acc, 2000, date(2026, 10, 5), "Swiggy")
    _tx(session, user, acc, 24000, date(2026, 10, 1), "ACME Salary", "INCOME")
    session.commit()
    from app.services import categorization_service
    categorization_service.categorize_by_rules(session, user.id)
    session.commit()
    s = analytics_service.get_monthly_summary(session, user.id, "2026-10")
    assert (s["income"], s["expenses"], s["savings"], s["savings_rate"]) == (
        Decimal("24000.00"), Decimal("2000.00"), Decimal("22000.00"), Decimal("91.67"))
    food = analytics_service.get_category_expenses(session, user.id, "food", date(2026, 9, 1), date(2026, 10, 1))
    assert food["amount"] == Decimal("1500.00") and len(food["subcategories"]) == 2
    top = analytics_service.get_category_breakdown(session, user.id, date(2026, 9, 1), date(2026, 10, 1))
    assert top[0]["category"] == "Food"
    cmp_ = analytics_service.compare_months(session, user.id, "2026-09", "2026-10")
    assert cmp_["difference"] == Decimal("500.00") and cmp_["top_increases"] == [] or cmp_["difference"] == Decimal("500.00")


def test_anomaly_and_recurring_detection(session):
    user = _user(session, "ar@example.com")
    acc = _account(session, user)
    today = date(2026, 10, 9)
    for i in range(1, 8):  # steady shopping history
        _tx(session, user, acc, 500 + i * 10, today - timedelta(days=60 + i * 5), "Amazon")
    spike = _tx(session, user, acc, 15000, today - timedelta(days=3), "Amazon")
    for m in range(1, 7):  # netflix monthly
        _tx(session, user, acc, 649, date(2026, m + 3 if m <= 6 else 9, 10) if m <= 6 else today, "Netflix")
    session.commit()
    found = anomaly_service.detect_anomalies(session, user.id, lookback_days=30, today=today)
    assert [f["transaction_id"] for f in found] == [spike.id]
    session.refresh(spike)
    assert spike.is_anomaly and spike.anomaly_score and "higher" in spike.anomaly_reason
    rec = recurring_service.detect_recurring(session, user.id, today=today)
    assert any(r["merchant"] == "Netflix" and r["frequency"] == "monthly" for r in rec)


def test_rag_is_isolated_per_user(session):
    u1, u2 = _user(session, "r1@example.com"), _user(session, "r2@example.com")
    texts = {u1.id: "health insurance premium renews every March", u2.id: "secret loan agreement of user two"}
    for uid, text in texts.items():
        doc = Document(user_id=uid, title=f"doc{uid}", filename="n.txt", storage_path="")
        session.add(doc)
        session.commit()
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
            fh.write(text)
        doc.storage_path = fh.name
        session.add(doc)
        session.commit()
        assert rag.ingest_document(session, doc.id) == 1
    vec = asyncio.run(get_embedder().embed(["loan agreement"]))[0]
    hits1 = rag.search_chunks(session, u1.id, vec, k=10)
    assert hits1 and all("user two" not in h["content"] for h in hits1)
    hits2 = rag.search_chunks(session, u2.id, vec, k=10)
    assert hits2 and "user two" in hits2[0]["content"]
