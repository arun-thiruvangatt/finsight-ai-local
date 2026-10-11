"""Transaction categorisation: deterministic rules first, LLM only for what is left."""
import asyncio
import logging
import re
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlmodel import Session

from app.ai import provider as provider_mod
from app.db.models import Category, Transaction

log = logging.getLogger(__name__)

# (regex, parent category, child category | None). Order matters: first match wins.
EXPENSE_RULES: list[tuple[str, str, str | None]] = [
    (r"swiggy|zomato|uber ?eats|eatsure|food ?panda|dunzo food", "Food", "Food Delivery"),
    (r"bigbasket|blinkit|zepto|dmart|d-mart|grofers|instamart|jiomart|reliance fresh|more supermarket|grocer",
     "Food", "Groceries"),
    (r"restaurant|cafe|café|starbucks|mcdonald|domino|kfc|pizza|burger|barbeque|biryani|dining|haldiram|chaayos|subway",
     "Food", "Restaurants"),
    (r"uber|ola ?cabs?|olacabs|rapido|meru|blu ?smart|indrive", "Transport", "Cab"),
    (r"irctc|metro|redbus|dmrc|bmtc|railway", "Transport", "Public Transport"),
    (r"petrol|diesel|fuel|hpcl|bpcl|iocl|indian oil|bharat petroleum|shell|nayara", "Transport", "Fuel"),
    (r"netflix|spotify|hotstar|prime video|youtube|bookmyshow|pvr|inox|sony ?liv|zee5|gaana|apple music|steam|playstation",
     "Entertainment", None),
    (r"amazon|flipkart|myntra|ajio|nykaa|meesho|tata ?cliq|croma|decathlon|ikea|lifestyle|zara|h&m|shoppers stop",
     "Shopping", None),
    (r"electricity|bescom|tneb|tangedco|msedcl|torrent power|adani electric|tata power|bses|cesc|kseb",
     "Bills", "Electricity"),
    (r"act ?fibernet|hathway|broadband|wifi|internet|excitel|tikona", "Bills", "Internet"),
    (r"airtel|jio|vodafone|vi prepaid|bsnl|mobile recharge|prepaid", "Bills", "Mobile"),
    (r"\brent\b|landlord|nobroker|housing\.com", "Bills", "Rent"),
    (r"apollo|pharmacy|pharmeasy|1mg|medplus|netmeds|hospital|clinic|diagnostic|practo|dental|thyrocare|\bdr\b\.?\s",
     "Healthcare", None),
]
INCOME_RULES: list[tuple[str, str, str | None]] = [
    (r"salary|payroll|sal credit|\bsal\b", "Salary", None),
    (r"interest|dividend|cashback|refund|int\.? ?pd", "Other Income", None),
]
_COMPILED = {
    "EXPENSE": [(re.compile(p, re.I), a, b) for p, a, b in EXPENSE_RULES],
    "INCOME": [(re.compile(p, re.I), a, b) for p, a, b in INCOME_RULES],
}
RULE_CONFIDENCE = 0.95
LLM_MIN_CONFIDENCE = 0.6


@dataclass
class RuleMatch:
    parent: str
    child: str | None
    confidence: float = RULE_CONFIDENCE


def match_rule(merchant: str | None, description: str | None, transaction_type: str) -> RuleMatch | None:
    if transaction_type == "TRANSFER":
        return RuleMatch("Transfers", None, 0.9)
    text = f"{merchant or ''} {description or ''}".strip()
    if not text:
        return None
    for rx, parent, child in _COMPILED.get(transaction_type, []):
        if rx.search(text):
            return RuleMatch(parent, child)
    return None


def build_category_index(session: Session, user_id: int) -> dict[tuple[str | None, str], int]:
    """Maps (parent_name|None, name) lower-cased -> category id."""
    cats = list(session.execute(select(Category).where(Category.user_id == user_id)).scalars())
    by_id = {c.id: c for c in cats}
    index: dict[tuple[str | None, str], int] = {}
    for c in cats:
        parent = by_id[c.parent_id].name.lower() if c.parent_id in by_id else None
        index[(parent, c.name.lower())] = c.id
    return index


def resolve_category_id(index: dict, parent: str, child: str | None) -> int | None:
    if child and (parent.lower(), child.lower()) in index:
        return index[(parent.lower(), child.lower())]
    return index.get((None, parent.lower()))


def _uncategorized(session: Session, user_id: int, tx_ids: list[int] | None, import_job_id: int | None,
                   limit: int | None):
    q = select(Transaction.id, Transaction.merchant, Transaction.description, Transaction.transaction_type,
               Transaction.amount).where(Transaction.user_id == user_id, Transaction.category_id.is_(None))
    if tx_ids is not None:
        q = q.where(Transaction.id.in_(tx_ids))
    if import_job_id is not None:
        q = q.where(Transaction.import_job_id == import_job_id)
    q = q.order_by(Transaction.id)
    if limit:
        q = q.limit(limit)
    return session.execute(q).all()


def categorize_by_rules(session: Session, user_id: int, tx_ids: list[int] | None = None,
                        import_job_id: int | None = None, limit: int | None = None) -> int:
    """Apply the rule engine to uncategorised transactions. Returns number categorised. No commit."""
    rows = _uncategorized(session, user_id, tx_ids, import_job_id, limit)
    if not rows:
        return 0
    index = build_category_index(session, user_id)
    groups: dict[tuple[int, float], list[int]] = {}
    for r in rows:
        m = match_rule(r.merchant, r.description, r.transaction_type)
        if not m:
            continue
        cid = resolve_category_id(index, m.parent, m.child)
        if cid:
            groups.setdefault((cid, m.confidence), []).append(r.id)
    done = 0
    for (cid, conf), ids in groups.items():
        session.execute(update(Transaction).where(Transaction.id.in_(ids), Transaction.user_id == user_id)
                        .values(category_id=cid, ai_category_source="rule", ai_category_confidence=conf))
        done += len(ids)
    return done


# ------------------------------- LLM stage ---------------------------------
_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "category": {"type": "string"}, "confidence": {"type": "number"}},
        "required": ["id", "category", "confidence"]}}},
    "required": ["results"],
}


async def _llm_classify(provider, rows: list, labels: list[str]) -> dict[int, tuple[str, float]]:
    system = ("You classify bank transactions into the user's categories. Choose ONLY from the allowed list. "
              "Use low confidence when unsure. Never invent categories.")
    payload = "Allowed categories:\n" + "\n".join(f"- {label}" for label in labels) + "\n\nTransactions:\n" + "\n".join(
        f"{r.id}: merchant={r.merchant!r} description={r.description!r} type={r.transaction_type} amount={r.amount}"
        for r in rows)
    out = await provider.generate_structured([{"role": "user", "content": payload}], _SCHEMA, system=system)
    res: dict[int, tuple[str, float]] = {}
    for item in out.get("results", []):
        try:
            res[int(item["id"])] = (str(item["category"]), float(item["confidence"]))
        except (KeyError, TypeError, ValueError):
            continue
    return res


def categorize_by_llm(session: Session, user_id: int, rows: list, batch_size: int = 25) -> int:
    provider = provider_mod.get_provider()
    if provider is None or not rows:
        return 0
    cats = list(session.execute(select(Category).where(Category.user_id == user_id)).scalars())
    by_id = {c.id: c for c in cats}
    label_to_id: dict[str, int] = {}
    for c in cats:
        label = f"{by_id[c.parent_id].name} > {c.name}" if c.parent_id in by_id else c.name
        label_to_id[label] = c.id
    labels = sorted(label_to_id)
    done = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        try:
            picks = asyncio.run(_llm_classify(provider, batch, labels))
        except Exception as exc:  # provider failure must never break the pipeline
            log.warning("LLM categorisation failed", extra={"error": type(exc).__name__})
            break
        for r in batch:
            label, conf = picks.get(r.id, ("", 0.0))
            cid = label_to_id.get(label)
            if cid and conf >= LLM_MIN_CONFIDENCE:
                session.execute(update(Transaction).where(Transaction.id == r.id, Transaction.user_id == user_id)
                                .values(category_id=cid, ai_category_source="llm",
                                        ai_category_confidence=max(0.0, min(conf, 1.0))))
                done += 1
    return done


def categorize_transactions(session: Session, user_id: int, tx_ids: list[int] | None = None,
                            use_llm: bool = True, limit: int = 500) -> dict:
    by_rules = categorize_by_rules(session, user_id, tx_ids, limit=limit)
    by_llm = 0
    if use_llm:
        remaining = _uncategorized(session, user_id, tx_ids, None, limit)
        by_llm = categorize_by_llm(session, user_id, remaining)
    session.commit()
    return {"by_rules": by_rules, "by_llm": by_llm}
