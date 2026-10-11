from decimal import Decimal

from tests.conftest import add_tx, category_id


def test_accounts_crud(client, auth):
    a = client.post("/api/v1/accounts", json={"name": "HDFC", "account_type": "BANK"}, headers=auth).json()
    assert client.patch(f"/api/v1/accounts/{a['id']}", json={"name": "HDFC Savings"}, headers=auth).json()["name"] == "HDFC Savings"
    assert len(client.get("/api/v1/accounts", headers=auth).json()) == 1
    assert client.delete(f"/api/v1/accounts/{a['id']}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/accounts/{a['id']}", headers=auth).json()["error"]["code"] == "ACCOUNT_NOT_FOUND"


def test_default_categories_and_tree(client, auth):
    tree = client.get("/api/v1/categories/tree", headers=auth).json()
    food = next(c for c in tree if c["name"] == "Food")
    assert {c["name"] for c in food["children"]} == {"Groceries", "Restaurants", "Food Delivery"}
    new = client.post("/api/v1/categories", json={"name": "Pets", "parent_id": None}, headers=auth)
    assert new.status_code == 201
    assert client.post("/api/v1/categories", json={"name": "pets"}, headers=auth).status_code == 409
    assert client.delete(f"/api/v1/categories/{category_id(client, auth, 'Food')}", headers=auth).status_code == 403


def test_transaction_lifecycle_updates_balance_and_filters(client, auth, account):
    t = add_tx(client, auth, account["id"], "250.50", "EXPENSE", "2026-09-03", "Swiggy")
    assert t["amount"] == 250.5 and t["category_id"] is not None and t["ai_category_source"] == "rule"
    add_tx(client, auth, account["id"], "24000", "INCOME", "2026-09-01", "ACME Salary")
    bal = client.get(f"/api/v1/accounts/{account['id']}", headers=auth).json()["current_balance"]
    assert Decimal(str(bal)) == Decimal("24749.50")

    page = client.get("/api/v1/transactions?transaction_type=EXPENSE&min_amount=100&search=swig&page_size=5", headers=auth).json()
    assert page["total"] == 1 and page["items"][0]["merchant"] == "Swiggy"
    assert client.get("/api/v1/transactions?sort=amount&order=asc", headers=auth).json()["items"][0]["amount"] == 250.5
    assert client.get("/api/v1/transactions?sort=password", headers=auth).status_code == 422

    client.patch(f"/api/v1/transactions/{t['id']}", json={"amount": "300.00"}, headers=auth)
    bal = client.get(f"/api/v1/accounts/{account['id']}", headers=auth).json()["current_balance"]
    assert Decimal(str(bal)) == Decimal("24700.00")
    assert client.delete(f"/api/v1/transactions/{t['id']}", headers=auth).status_code == 204
    bal = client.get(f"/api/v1/accounts/{account['id']}", headers=auth).json()["current_balance"]
    assert Decimal(str(bal)) == Decimal("25000.00")
    assert client.get(f"/api/v1/transactions/{t['id']}", headers=auth).json()["error"]["code"] == "TRANSACTION_NOT_FOUND"


def test_money_rejects_bad_amounts(client, auth, account):
    for amount in ("0", "-5", "1.234", "abc"):
        r = client.post("/api/v1/transactions", headers=auth, json={
            "account_id": account["id"], "amount": amount, "transaction_type": "EXPENSE", "transaction_date": "2026-09-03"})
        assert r.status_code == 422, amount


def test_budgets_and_goals(client, auth, account):
    from datetime import date
    today = date.today()
    add_tx(client, auth, account["id"], "4800", "EXPENSE", today.isoformat(), "Swiggy")
    b = client.post("/api/v1/budgets", headers=auth, json={
        "category_id": category_id(client, auth, "Food"), "name": "Food", "amount": "6000",
        "start_date": today.replace(day=1).isoformat()}).json()
    st = client.get(f"/api/v1/budgets/{b['id']}/status", headers=auth).json()
    assert (st["budget"], st["spent"], st["remaining"], st["usage_percentage"]) == (6000, 4800, 1200, 80)
    assert st["warnings"]  # 80% threshold reached
    assert client.post("/api/v1/budgets", headers=auth, json={
        "name": "x", "amount": "10", "period": "CUSTOM", "start_date": today.isoformat()}).status_code == 422

    g = client.post("/api/v1/goals", headers=auth, json={"name": "Laptop", "target_amount": "60000",
                                                         "current_amount": "15000"}).json()
    p = client.get(f"/api/v1/goals/{g['id']}/progress", headers=auth).json()
    assert (p["remaining_amount"], p["progress_percentage"]) == (45000, 25)
    assert "estimate" in p["projection_note"].lower() or "not enough" in p["projection_note"].lower()


def test_analytics_endpoints(client, auth, account):
    from app.utils.dates import month_str, previous_month
    from datetime import date
    cur = month_str(date.today())
    prev = previous_month(cur)
    add_tx(client, auth, account["id"], "24000", "INCOME", f"{cur}-01", "ACME Salary")
    add_tx(client, auth, account["id"], "6000", "EXPENSE", f"{cur}-02", "Swiggy")
    add_tx(client, auth, account["id"], "1000", "EXPENSE", f"{prev}-02", "Swiggy")
    m = client.get(f"/api/v1/analytics/monthly?month={cur}", headers=auth).json()
    assert m == {"month": cur, "income": 24000, "expenses": 6000, "savings": 18000, "savings_rate": 75}
    cats = client.get(f"/api/v1/analytics/categories?month={cur}", headers=auth).json()
    assert cats[0]["category"] == "Food" and cats[0]["percentage"] == 100
    cf = client.get("/api/v1/analytics/cashflow?months=3", headers=auth).json()
    assert len(cf) == 3 and cf[-1]["net"] == 18000
    assert client.get("/api/v1/analytics/merchants", headers=auth).json()[0]["merchant"] == "Swiggy"
    cmp_ = client.get(f"/api/v1/analytics/compare?previous={prev}&current={cur}", headers=auth).json()
    assert cmp_["difference"] == 5000 and cmp_["top_increases"][0]["category"] == "Food"


def test_csv_import_endpoint_end_to_end(client, auth, account):
    csv = (b"Date,Description,Amount,Type,Reference\n2026-09-01,ACME Salary,24000,credit,R1\n"
           b"2026-09-02,Swiggy,250,debit,R2\n")
    up = client.post("/api/v1/imports/csv", headers=auth, data={"account_id": account["id"]},
                     files={"file": ("sept.csv", csv, "text/csv")})
    assert up.status_code == 202, up.text
    job = client.get(f"/api/v1/imports/{up.json()['id']}", headers=auth).json()
    assert job["status"] == "COMPLETED" and job["successful_rows"] == 2
    again = client.post("/api/v1/imports/csv", headers=auth, data={"account_id": account["id"]},
                        files={"file": ("sept.csv", csv, "text/csv")}).json()
    assert again["duplicate_rows"] == 2 and again["successful_rows"] == 0
    # custom mapping
    odd = b"When,What,How much\n2026-09-05,Uber,-120\n"
    r = client.post("/api/v1/imports/csv", headers=auth, data={
        "account_id": account["id"], "column_mapping": '{"date":"When","description":"What","amount":"How much"}'},
        files={"file": ("odd.csv", odd, "text/csv")})
    assert r.json()["successful_rows"] == 1
    # restrictions
    assert client.post("/api/v1/imports/csv", headers=auth, data={"account_id": account["id"]},
                       files={"file": ("evil.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/v1/imports/csv", headers=auth, data={"account_id": account["id"]},
                       files={"file": ("empty.csv", b"", "text/csv")}).status_code == 400
    assert client.post("/api/v1/imports/csv", headers=auth, data={"account_id": account["id"], "column_mapping": "[1]"},
                       files={"file": ("a.csv", csv, "text/csv")}).json()["error"]["code"] == "INVALID_MAPPING"
