from typing import TypeVar

from sqlmodel import Session, SQLModel

from app.core.exceptions import not_found

M = TypeVar("M", bound=SQLModel)


def get_owned(session: Session, model: type[M], obj_id: int, user_id: int, entity: str) -> M:
    """Fetch a row only if it belongs to user_id. Foreign rows look exactly like missing rows (404)."""
    obj = session.get(model, obj_id)
    if obj is None or getattr(obj, "user_id", None) != user_id:
        raise not_found(entity)
    return obj
