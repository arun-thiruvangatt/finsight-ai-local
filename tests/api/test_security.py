from tests.conftest import add_tx


def test_user_b_cannot_touch_user_a_resources(client, auth, auth_b, account):
    tx = add_tx(client, auth, account["id"], "100", "EXPENSE", "2026-09-03", "Swiggy")
    a_cat = client.get("/api/v1/categories", headers=auth).json()[0]["id"]
    goal = client.post("/api/v1/goals", headers=auth, json={"name": "G", "target_amount": "100"}).json()

    # accounts
    assert client.get(f"/api/v1/accounts/{account['id']}", headers=auth_b).status_code == 404
    assert client.patch(f"/api/v1/accounts/{account['id']}", json={"name": "hack"}, headers=auth_b).status_code == 404
    assert client.delete(f"/api/v1/accounts/{account['id']}", headers=auth_b).status_code == 404
    assert client.get("/api/v1/accounts", headers=auth_b).json() == []
    # transactions
    assert client.get(f"/api/v1/transactions/{tx['id']}", headers=auth_b).status_code == 404
    assert client.patch(f"/api/v1/transactions/{tx['id']}", json={"merchant": "x"}, headers=auth_b).status_code == 404
    assert client.delete(f"/api/v1/transactions/{tx['id']}", headers=auth_b).status_code == 404
    assert client.get("/api/v1/transactions", headers=auth_b).json()["total"] == 0
    # cannot post into someone else's account / category
    body = {"account_id": account["id"], "amount": "5", "transaction_type": "EXPENSE", "transaction_date": "2026-09-03"}
    assert client.post("/api/v1/transactions", json=body, headers=auth_b).status_code == 404
    b_acc = client.post("/api/v1/accounts", json={"name": "B"}, headers=auth_b).json()
    body.update(account_id=b_acc["id"], category_id=a_cat)
    assert client.post("/api/v1/transactions", json=body, headers=auth_b).status_code == 404
    # goals + analytics see nothing
    assert client.get(f"/api/v1/goals/{goal['id']}", headers=auth_b).status_code == 404
    assert client.get("/api/v1/analytics/merchants?month=2026-09", headers=auth_b).json() == []
    # admin-only
    assert client.get("/api/v1/users", headers=auth).status_code == 403


def test_user_b_cannot_access_user_a_documents(client, auth, auth_b):
    up = client.post("/api/v1/documents", headers=auth, data={"title": "Plan"},
                     files={"file": ("plan.txt", b"My secret emergency fund plan: keep 6 months of expenses.", "text/plain")})
    assert up.status_code == 202 and up.json()["status"] == "READY"
    doc_id = up.json()["id"]
    assert client.get("/api/v1/documents", headers=auth_b).json() == []
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=auth_b).status_code == 404
    assert client.post("/api/v1/ai/search", headers=auth_b, json={"query": "emergency fund plan"}).json() == []
    hits = client.post("/api/v1/ai/search", headers=auth, json={"query": "emergency fund plan"}).json()
    assert hits and hits[0]["document_id"] == doc_id
    ask = client.post("/api/v1/ai/ask", headers=auth_b, json={"question": "what does my emergency fund plan say"}).json()
    assert "secret" not in ask["answer"]
    assert client.delete(f"/api/v1/documents/{doc_id}", headers=auth).status_code == 204


def test_conversations_are_private(client, auth, auth_b):
    conv = client.post("/api/v1/ai/ask", headers=auth, json={"question": "how much did I spend"}).json()["conversation_id"]
    assert client.get(f"/api/v1/ai/conversations/{conv}/messages", headers=auth).status_code == 200
    assert client.get(f"/api/v1/ai/conversations/{conv}/messages", headers=auth_b).status_code == 404
    assert client.post("/api/v1/ai/ask", headers=auth_b, json={"question": "hello there", "conversation_id": conv}).status_code == 404


def test_upload_rules(client, auth):
    bad = client.post("/api/v1/documents", headers=auth, files={"file": ("x.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 400
    assert client.post("/api/v1/documents", headers=auth,
                       files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
