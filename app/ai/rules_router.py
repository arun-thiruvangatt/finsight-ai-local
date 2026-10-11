"""Deterministic assistant: maps a question to tools with keyword rules and renders the answer
from tool output. Used when no LLM is configured or the provider fails."""
import re
from datetime import date

from app.utils.dates import parse_month_mentions, previous_month
from app.utils.money import format_inr


def _has(q: str, *words: str) -> bool:
    return any(re.search(rf"\b{w}", q) for w in words)


def plan(question: str, today: date, category_names: list[str]) -> list[tuple[str, dict]]:
    q = question.lower()
    months = parse_month_mentions(q, today)
    cat = next((c for c in sorted(category_names, key=len, reverse=True) if re.search(rf"\b{re.escape(c.lower())}\b", q)), None)
    month_arg = {"month": months[0]} if months else {}

    if _has(q, "unusual", "anomal", "suspicious", "strange", "odd transaction"):
        return [("get_anomalies", {})]
    if _has(q, "recurring", "subscription", "repeat"):
        return [("get_recurring_expenses", {})]
    if _has(q, "budget", "on track"):
        return [("get_budget_status", {"category": cat} if cat else {})]
    if _has(q, "goal", "allocate", "saving for", "save toward"):
        return [("get_goal_status", {})]
    if _has(q, "compar", "versus", "vs", "why", "increase", "decrease", "difference") and \
            _has(q, "spend", "expens", "increase", "decrease", "compar", "vs", "versus"):
        if len(months) >= 2:
            ms = sorted(months[:2])
            return [("compare_months", {"previous_month": ms[0], "current_month": ms[1]})]
        if len(months) == 1:
            return [("compare_months", {"current_month": months[0], "previous_month": previous_month(months[0])})]
        return [("compare_months", {})]
    if _has(q, "merchant", "where do i spend", "where did i spend", "top spend", "most money"):
        return [("get_top_merchants", month_arg)]
    if _has(q, "cash ?flow"):
        return [("get_cashflow", {"months": 6})]
    if _has(q, "trend", "over time", "history"):
        return [("get_category_trends", {"category": cat, "months": 6} if cat else {"months": 6})]
    if _has(q, "income", "earn", "salary", "make", "made"):
        return [("get_income_summary", month_arg)]
    if cat and _has(q, "spen", "expens", "cost", "paid", "pay", "how much"):
        return [("get_category_expenses", {"category": cat, **month_arg})]
    if _has(q, "spen", "expens", "saving", "savings", "summary", "how much"):
        return [("get_monthly_summary", month_arg)]
    if _has(q, "transaction", "show", "list", "latest", "recent"):
        return [("get_transactions", {"limit": 10, **({"category": cat} if cat else {})})]
    return [("search_documents", {"query": question})]


def _money(v) -> str:
    return format_inr(v)


def render(tool: str, r: dict) -> str:
    if "error" in r:
        return f"I couldn't complete that: {r['error']}"
    if tool == "get_monthly_summary":
        return (f"In {r['month']} you earned {_money(r['income'])} and spent {_money(r['expenses'])}, "
                f"saving {_money(r['savings'])} (savings rate {r['savings_rate']}%).")
    if tool == "get_category_expenses":
        lines = [f"You spent {_money(r['amount'])} on {r['category']} ({r['period']}) across "
                 f"{r['transaction_count']} transactions."]
        if len(r["subcategories"]) > 1:
            lines += [f"- {s['category']}: {_money(s['amount'])}" for s in r["subcategories"]]
        return "\n".join(lines)
    if tool == "compare_months":
        p, c = r["previous_month"], r["current_month"]
        direction = "increased" if r["difference"] > 0 else "decreased" if r["difference"] < 0 else "did not change"
        pct = f" ({r['percentage_change']:+}%)" if r["percentage_change"] is not None else ""
        lines = [f"Spending {direction} from {_money(p['expenses'])} ({p['month']}) to {_money(c['expenses'])} "
                 f"({c['month']}): {_money(abs(r['difference']))}{pct}."]
        if r["top_increases"]:
            lines.append("Biggest increases:")
            lines += [f"- {i['category']}: +{_money(i['difference'])}" for i in r["top_increases"][:3]]
        if r["top_decreases"]:
            lines.append("Biggest decreases:")
            lines += [f"- {i['category']}: -{_money(abs(i['difference']))}" for i in r["top_decreases"][:3]]
        return "\n".join(lines)
    if tool == "get_budget_status":
        if not r["budgets"]:
            return "You have no active budgets yet."
        lines = []
        for b in r["budgets"]:
            lines.append(f"{b['name']}: {_money(b['spent'])} of {_money(b['budget'])} used ({b['usage_percentage']}%), "
                         f"{_money(b['remaining'])} left; projected {_money(b['projected_spending'])} (estimate).")
            lines += [f"  ! {w}" for w in b["warnings"]]
        return "\n".join(lines)
    if tool == "get_goal_status":
        if not r["goals"]:
            return "You have no active goals yet."
        out = []
        for g in r["goals"]:
            s = (f"{g['name']}: {g['progress_percentage']}% done, {_money(g['remaining_amount'])} remaining. "
                 f"Average monthly savings {_money(g['avg_monthly_savings'])}; a cautious allocation estimate is "
                 f"{_money(g['safe_allocation_estimate'])}/month.")
            if g["required_monthly_contribution"] is not None:
                s += f" Required to meet the target date: {_money(g['required_monthly_contribution'])}/month."
            if g["projected_completion"]:
                s += f" Projected completion (estimate): {g['projected_completion']}."
            out.append(s)
        return "\n".join(out)
    if tool == "get_recurring_expenses":
        if not r["recurring"]:
            return "No recurring expenses detected yet. Run detection after importing a few months of data."
        lines = [f"- {i['merchant']}: {_money(i['average_amount'])} {i['frequency']} (confidence {i['confidence']})"
                 for i in r["recurring"][:8]]
        return f"Your recurring expenses (about {_money(r['estimated_monthly_total'])}/month):\n" + "\n".join(lines)
    if tool == "get_anomalies":
        if not r["anomalies"]:
            return "No unusual transactions flagged."
        return "Unusual transactions:\n" + "\n".join(
            f"- {a['date']} {a['merchant'] or 'Unknown'} {_money(a['amount'])}: {a['reason']}" for a in r["anomalies"])
    if tool == "get_top_merchants":
        if not r["merchants"]:
            return f"No spending found for {r['period']}."
        return f"Top merchants ({r['period']}):\n" + "\n".join(
            f"- {m['merchant']}: {_money(m['amount'])} ({m['transaction_count']}x)" for m in r["merchants"])
    if tool == "get_cashflow":
        return "Cash flow by month:\n" + "\n".join(
            f"- {m['month']}: in {_money(m['income'])}, out {_money(m['expenses'])}, net {_money(m['net'])}"
            for m in r["months"])
    if tool == "get_category_trends":
        return f"Monthly spending – {r['category']}:\n" + "\n".join(
            f"- {m['month']}: {_money(m['expenses'])}" for m in r["months"])
    if tool == "get_income_summary":
        return f"Income for {r['period']}: {_money(r['total'])} across {r['transaction_count']} transactions."
    if tool == "get_transactions":
        if not r["transactions"]:
            return "No matching transactions."
        return f"{r['total_matching']} matching, showing {r['returned']}:\n" + "\n".join(
            f"- {t['date']} {t['merchant'] or t['description'] or '-'}: {_money(t['amount'])} ({t['type']})"
            for t in r["transactions"])
    if tool == "search_documents":
        if not r["matches"]:
            return ("I couldn't match that to your finances or documents. Try asking about spending, budgets, "
                    "goals, recurring expenses or unusual transactions.")
        return "From your documents:\n" + "\n".join(
            f"- [{m['document_title']}] {m['content'][:300]}" for m in r["matches"])
    return "Done."

