"""Development seed: demo user + accounts + ~6 months of synthetic INR transactions (no real data).

    python -m scripts.seed            # create demo data (no-op if the demo user exists)
    python -m scripts.seed --reset    # wipe and recreate the demo user's data
Login: demo@finsight.dev / Demo@12345
"""
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, update
from sqlmodel import Session, select

from app.ai import rag
from app.core.config import get_settings
from app.db.engine import engine
from app.db.models import (Account, AIInsight, AuditLog, Budget, Category, Conversation, ConversationMessage,
                           Document, DocumentChunk, FinancialGoal, ImportJob, RecurringTransaction, RefreshToken,
                           Transaction, User)
from app.schemas.auth import RegisterRequest
from app.services import (anomaly_service, auth_service, categorization_service, insight_service,
                          recurring_service)
from app.services.transaction_service import balance_delta
from app.utils.dates import add_months
from app.utils.money import quantize

EMAIL, PASSWORD = "demo@finsight.dev", "Demo@12345"


def _wipe(session: Session, user_id: int) -> None:
    conv_ids = session.exec(select(Conversation.id).where(Conversation.user_id == user_id)).all()
    if conv_ids:
        session.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(conv_ids)))
    for model in (Conversation, DocumentChunk, Document, AIInsight, RecurringTransaction, Transaction, ImportJob,
                  Budget, FinancialGoal):
        session.execute(delete(model).where(model.user_id == user_id))
    session.execute(update(Category).where(Category.user_id == user_id).values(parent_id=None))
    for model in (Category, Account, RefreshToken, AuditLog):
        session.execute(delete(model).where(model.user_id == user_id))
    session.execute(delete(User).where(User.id == user_id))
    session.commit()


def _amount(rng: random.Random, lo: int, hi: int) -> Decimal:
    return quantize(Decimal(rng.randrange(lo * 100, hi * 100)) / 100)


def build_transactions(rng: random.Random, today: date) -> list[dict]:
    rows: list[dict] = []

    def add(d: date, acct: str, ttype: str, amount: Decimal, merchant: str, desc: str) -> None:
        if d <= today:
            rows.append({"date": d, "acct": acct, "type": ttype, "amount": amount, "merchant": merchant, "desc": desc})

    for back in range(5, -1, -1):
        m = add_months(today.replace(day=1), -back)

        def day(n: int, m=m) -> date:
            return date(m.year, m.month, min(n, 28))

        add(day(1), "hdfc", "INCOME", Decimal("24000.00"), "ACME Corp", "ACME Corp Salary Credit")
        add(day(2), "hdfc", "EXPENSE", Decimal("5500.00"), "Landlord", "Rent - Landlord")
        add(day(5), "hdfc", "EXPENSE", _amount(rng, 1500, 2100), "BESCOM", "BESCOM Electricity Bill")
        add(day(6), "hdfc", "EXPENSE", Decimal("699.00"), "ACT Fibernet", "ACT Fibernet Broadband")
        add(day(7), "hdfc", "EXPENSE", Decimal("399.00"), "Airtel", "Airtel Prepaid Recharge")
        add(day(10), "icici", "EXPENSE", Decimal("649.00"), "Netflix", "Netflix Subscription")
        add(day(12), "icici", "EXPENSE", Decimal("119.00"), "Spotify", "Spotify Premium")
        for _ in range(rng.randint(6, 9)):
            add(day(rng.randint(1, 28)), "icici", "EXPENSE", _amount(rng, 180, 450),
                rng.choice(["Swiggy", "Zomato"]), "Food delivery order")
        for _ in range(rng.randint(3, 4)):
            add(day(rng.randint(1, 28)), "hdfc", "EXPENSE", _amount(rng, 300, 900),
                rng.choice(["BigBasket", "Blinkit", "DMart"]), "Groceries")
        for _ in range(rng.randint(2, 3)):
            add(day(rng.randint(1, 28)), "icici", "EXPENSE", _amount(rng, 200, 900),
                rng.choice(["Starbucks", "Dominos Pizza", "Chaayos"]), "Eating out")
        for _ in range(rng.randint(4, 6)):
            add(day(rng.randint(1, 28)), "cash", "EXPENSE", _amount(rng, 90, 350),
                rng.choice(["Uber", "Ola Cabs", "Rapido"]), "Cab ride")
        for _ in range(rng.randint(1, 2)):
            add(day(rng.randint(1, 28)), "icici", "EXPENSE", _amount(rng, 500, 1500), "HPCL Petrol Pump", "Fuel")
        for _ in range(rng.randint(1, 2)):
            add(day(rng.randint(1, 28)), "icici", "EXPENSE", _amount(rng, 400, 1400),
                rng.choice(["Amazon", "Flipkart", "Myntra"]), "Online shopping")
        if rng.random() < 0.5:
            add(day(rng.randint(1, 28)), "hdfc", "EXPENSE", _amount(rng, 250, 800), "Apollo Pharmacy", "Medicines")
        add(day(rng.randint(1, 28)), "cash", "EXPENSE", _amount(rng, 100, 300), "Local Kirana Store", "Misc purchase")

    # one clearly unusual purchase inside the anomaly look-back window
    add(today - timedelta(days=4), "icici", "EXPENSE", Decimal("18999.00"), "Amazon", "Amazon - electronics")
    return rows


def main() -> None:
    reset = "--reset" in sys.argv
    rng = random.Random(42)  # deterministic
    today = date.today()
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == EMAIL)).first()
        if existing and not reset:
            print(f"Demo user already exists ({EMAIL}). Use --reset to recreate.")
            return
        if existing:
            _wipe(session, existing.id)
        user = auth_service.register(session, RegisterRequest(email=EMAIL, password=PASSWORD, full_name="Demo User"))
        uid = user.id

        accounts = {
            "hdfc": Account(user_id=uid, name="HDFC Savings", account_type="BANK", institution="HDFC Bank",
                            current_balance=Decimal("50000.00")),
            "icici": Account(user_id=uid, name="ICICI Credit Card", account_type="CREDIT_CARD",
                             institution="ICICI Bank", current_balance=Decimal("0.00")),
            "cash": Account(user_id=uid, name="Cash", account_type="CASH", current_balance=Decimal("2000.00")),
        }
        session.add_all(accounts.values())
        session.flush()

        txs = []
        for r in build_transactions(rng, today):
            acc = accounts[r["acct"]]
            acc.current_balance += balance_delta(r["type"], r["amount"])
            txs.append(Transaction(user_id=uid, account_id=acc.id, amount=r["amount"], transaction_type=r["type"],
                                   merchant=r["merchant"], description=r["desc"], transaction_date=r["date"],
                                   currency="INR"))
        session.add_all(txs)
        session.commit()

        stats = categorization_service.categorize_transactions(session, uid, use_llm=False)
        cats = {c.name: c.id for c in session.exec(select(Category).where(Category.user_id == uid))}
        session.add_all([
            Budget(user_id=uid, category_id=cats["Food"], name="Food", amount=Decimal("6000"), start_date=today.replace(day=1)),
            Budget(user_id=uid, category_id=cats["Transport"], name="Transport", amount=Decimal("2500"), start_date=today.replace(day=1)),
            Budget(user_id=uid, category_id=cats["Shopping"], name="Shopping", amount=Decimal("3000"), start_date=today.replace(day=1)),
            FinancialGoal(user_id=uid, name="Emergency Fund", target_amount=Decimal("100000"),
                          current_amount=Decimal("20000"), target_date=add_months(today.replace(day=1), 12),
                          priority="HIGH"),
        ])
        session.commit()
        recurring_service.detect_recurring(session, uid)
        anomaly_service.detect_anomalies(session, uid)
        insight_service.generate_monthly_insights(session, uid)

        folder = Path(get_settings().UPLOAD_DIR) / "documents" / str(uid)
        folder.mkdir(parents=True, exist_ok=True)
        note = folder / "seed-financial-plan.txt"
        note.write_text(
            "Financial plan notes.\n\nEmergency fund: keep six months of expenses in a liquid savings account.\n\n"
            "Health insurance: family floater policy renews every March; premium is paid annually.\n\n"
            "Rent agreement: monthly rent of 5500 rupees, due on the 2nd, 11 month lease with 5 percent annual hike.\n")
        doc = Document(user_id=uid, title="Financial plan notes", filename=note.name, doc_type="PLAN",
                       storage_path=str(note))
        session.add(doc)
        session.commit()
        rag.ingest_document(session, doc.id)

    print(f"Seeded {len(txs)} transactions ({stats['by_rules']} auto-categorised by rules).")
    print(f"Login: {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
