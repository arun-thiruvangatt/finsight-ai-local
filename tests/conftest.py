"""Test configuration. Unit tests need no services. Integration/API tests need PostgreSQL with the
pgvector extension (TEST_DATABASE_URL, default: localhost finsight_test) and are skipped otherwise.
The LLM is never called: tests use no provider (rule router) or an in-process fake provider."""
import os
import tempfile

import pytest

TEST_DB = os.environ.get("TEST_DATABASE_URL",
                         "postgresql+psycopg://postgres:postgres@localhost:5432/finsight_test")
os.environ.update({
    "DATABASE_URL": TEST_DB, "APP_ENV": "test", "DEBUG": "true", "RATE_LIMIT_ENABLED": "false",
    "CELERY_EAGER": "true", "LLM_PROVIDER": "", "LLM_API_KEY": "", "LLM_MODEL": "", "EMBEDDING_PROVIDER": "",
    "EMBEDDING_DIM": "384", "JWT_SECRET_KEY": "test-secret-key-test-secret-key-1234567890",
    "UPLOAD_DIR": tempfile.mkdtemp(prefix="finsight-test-"),
})

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402


def _ensure_database() -> None:
    url = make_url(TEST_DB)
    try:
        with create_engine(url).connect():
            return
    except OperationalError:
        pass
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))


@pytest.fixture(scope="session")
def _db():
    try:
        _ensure_database()
        import app.db.models  # noqa: F401
        from app.db.engine import engine
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL with pgvector not available for DB tests: {exc}", allow_module_level=False)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)  # tests only; production uses Alembic
    yield engine
    engine.dispose()


@pytest.fixture
def session(_db):
    with Session(_db) as s:
        yield s
    tables = ", ".join(f'"{t.name}"' for t in SQLModel.metadata.sorted_tables)
    with _db.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(session):
    from fastapi.testclient import TestClient

    from app.main import app
    with TestClient(app) as c:
        yield c


def make_user(client, email: str, password: str = "password123") -> dict:
    r = client.post("/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Test User"})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client):
    return make_user(client, "a@example.com")


@pytest.fixture
def auth_b(client):
    return make_user(client, "b@example.com")


@pytest.fixture
def account(client, auth):
    r = client.post("/api/v1/accounts", json={"name": "Main", "account_type": "BANK", "current_balance": 1000}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def category_id(client, headers, name: str) -> int:
    cats = client.get("/api/v1/categories", headers=headers).json()
    return next(c["id"] for c in cats if c["name"] == name)


def add_tx(client, headers, account_id: int, amount, ttype: str, d: str, merchant: str | None = None,
           category: str | None = None):
    body = {"account_id": account_id, "amount": str(amount), "transaction_type": ttype, "transaction_date": d,
            "merchant": merchant}
    if category:
        body["category_id"] = category_id(client, headers, category)
    r = client.post("/api/v1/transactions", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
