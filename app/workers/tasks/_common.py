from sqlalchemy import select
from sqlmodel import Session

from app.db.models import User


def user_ids(session: Session, user_id: int | None) -> list[int]:
    if user_id is not None:
        return [user_id]
    return list(session.execute(select(User.id).where(User.is_active == True)).scalars())  # noqa: E712
