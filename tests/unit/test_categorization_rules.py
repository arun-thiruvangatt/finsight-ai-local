import pytest

from app.services.categorization_service import match_rule


@pytest.mark.parametrize("merchant,ttype,parent,child", [
    ("Swiggy", "EXPENSE", "Food", "Food Delivery"),
    ("Uber Eats", "EXPENSE", "Food", "Food Delivery"),
    ("UBER INDIA", "EXPENSE", "Transport", "Cab"),
    ("Netflix", "EXPENSE", "Entertainment", None),
    ("Amazon Prime Video", "EXPENSE", "Entertainment", None),
    ("Amazon", "EXPENSE", "Shopping", None),
    ("BESCOM Electricity", "EXPENSE", "Bills", "Electricity"),
    ("Apollo Pharmacy", "EXPENSE", "Healthcare", None),
    ("ACME Corp Salary Credit", "INCOME", "Salary", None),
    ("Savings interest", "INCOME", "Other Income", None),
    ("Anything", "TRANSFER", "Transfers", None),
])
def test_rules_match(merchant, ttype, parent, child):
    m = match_rule(merchant, None, ttype)
    assert m is not None and (m.parent, m.child) == (parent, child)


def test_unknown_merchant_unresolved():
    assert match_rule("Local Kirana Store", "Misc purchase", "EXPENSE") is None
    assert match_rule(None, None, "EXPENSE") is None
