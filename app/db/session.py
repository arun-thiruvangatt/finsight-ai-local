from collections.abc import Iterator

from sqlmodel import Session

from app.db.engine import engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request. Services commit explicitly."""
    with Session(engine) as session:
        yield session
