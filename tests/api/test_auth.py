from tests.conftest import make_user


def test_register_login_me_refresh_logout(client):
    r = client.post("/api/v1/auth/register", json={"email": "New@Example.com", "password": "password123", "full_name": "N"})
    assert r.status_code == 201 and r.json()["email"] == "new@example.com" and "password" not in r.text
    assert client.post("/api/v1/auth/register", json={"email": "new@example.com", "password": "password123",
                                                       "full_name": "N"}).json()["error"]["code"] == "EMAIL_ALREADY_REGISTERED"
    tokens = client.post("/api/v1/auth/login", json={"email": "new@example.com", "password": "password123"}).json()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200 and me.json()["currency"] == "INR" and me.json()["timezone"] == "Asia/Kolkata"

    new = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert new.status_code == 200
    # rotated token reuse is rejected and revokes the whole family
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401 and reuse.json()["error"]["code"] == "TOKEN_REUSED"
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new.json()["refresh_token"]}).status_code == 401


def test_logout_revokes_refresh_token(client):
    make_user(client, "x@example.com")
    t = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "password123"}).json()
    assert client.post("/api/v1/auth/logout", json={"refresh_token": t["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_bad_credentials_and_missing_token(client):
    make_user(client, "y@example.com")
    r = client.post("/api/v1/auth/login", json={"email": "y@example.com", "password": "wrong-password"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert client.get("/api/v1/accounts").status_code == 401
    assert client.get("/api/v1/accounts", headers={"Authorization": "Bearer junk"}).json()["error"]["code"] == "INVALID_TOKEN"
    # an refresh token must not work as an access token
    t = client.post("/api/v1/auth/login", json={"email": "y@example.com", "password": "password123"}).json()
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {t['refresh_token']}"}).status_code == 401


def test_validation_error_shape_and_health(client):
    r = client.post("/api/v1/auth/register", json={"email": "bad", "password": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert client.get("/health").json() == {"status": "ok"}
