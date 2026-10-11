from sqlalchemy import func
from sqlalchemy import update as sa_update
from sqlmodel import Session, select

from app.core.constants import DEFAULT_CATEGORIES
from app.core.exceptions import AppError, ConflictError, PermissionDeniedError
from app.db.models import Budget, Category, Transaction
from app.schemas.category import CategoryCreate, CategoryTree, CategoryUpdate
from app.services.common import get_owned


def ensure_default_categories(session: Session, user_id: int) -> None:
    if session.exec(select(Category.id).where(Category.user_id == user_id)).first():
        return
    for name, (ctype, children) in DEFAULT_CATEGORIES.items():
        parent = Category(user_id=user_id, name=name, category_type=ctype, is_system=True)
        session.add(parent)
        session.flush()
        for child in children:
            session.add(Category(user_id=user_id, name=child, parent_id=parent.id, category_type=ctype,
                                 is_system=True))
    session.flush()


def list_categories(session: Session, user_id: int) -> list[Category]:
    return list(session.exec(select(Category).where(Category.user_id == user_id).order_by(Category.name)))


def get_tree(session: Session, user_id: int) -> list[CategoryTree]:
    cats = list_categories(session, user_id)
    nodes = {c.id: CategoryTree.model_validate(c) for c in cats}
    roots: list[CategoryTree] = []
    for c in cats:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id].children.append(node)
        else:
            roots.append(node)
    return roots


def descendant_ids(session: Session, user_id: int, category_id: int) -> list[int]:
    rows = session.exec(select(Category.id, Category.parent_id).where(Category.user_id == user_id)).all()
    children: dict[int, list[int]] = {}
    for cid, pid in rows:
        if pid is not None:
            children.setdefault(pid, []).append(cid)
    out, stack = [], [category_id]
    while stack:
        cur = stack.pop()
        out.append(cur)
        stack.extend(children.get(cur, []))
    return out


def find_by_name(session: Session, user_id: int, name: str) -> Category | None:
    n = name.strip().lower()
    cat = session.exec(select(Category).where(Category.user_id == user_id, func.lower(Category.name) == n)
                       .order_by(Category.parent_id.is_(None).desc())).first()
    if cat:
        return cat
    return session.exec(select(Category).where(Category.user_id == user_id, Category.name.ilike(f"%{n}%"))
                        .order_by(Category.parent_id.is_(None).desc())).first()


def _validate_parent(session: Session, user_id: int, parent_id: int | None, self_id: int | None = None) -> None:
    if parent_id is None:
        return
    get_owned(session, Category, parent_id, user_id, "Category")
    if self_id is not None and parent_id in descendant_ids(session, user_id, self_id):
        raise AppError("A category cannot be its own ancestor.", code="CATEGORY_CYCLE")


def _check_duplicate(session: Session, user_id: int, name: str, parent_id: int | None, exclude_id: int | None = None):
    q = select(Category.id).where(Category.user_id == user_id, func.lower(Category.name) == name.strip().lower(),
                                  Category.parent_id.is_(None) if parent_id is None else Category.parent_id == parent_id)
    existing = session.exec(q).first()
    if existing and existing != exclude_id:
        raise ConflictError("A category with this name already exists here.", code="CATEGORY_ALREADY_EXISTS")


def create(session: Session, user_id: int, data: CategoryCreate) -> Category:
    _validate_parent(session, user_id, data.parent_id)
    _check_duplicate(session, user_id, data.name, data.parent_id)
    cat = Category(user_id=user_id, name=data.name.strip(), parent_id=data.parent_id,
                   category_type=data.category_type.value)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def update(session: Session, user_id: int, category_id: int, data: CategoryUpdate) -> Category:
    cat = get_owned(session, Category, category_id, user_id, "Category")
    changes = data.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        _validate_parent(session, user_id, changes["parent_id"], cat.id)
    _check_duplicate(session, user_id, changes.get("name", cat.name), changes.get("parent_id", cat.parent_id), cat.id)
    for k, v in changes.items():
        setattr(cat, k, v.value if hasattr(v, "value") else v)
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return cat


def delete(session: Session, user_id: int, category_id: int) -> None:
    cat = get_owned(session, Category, category_id, user_id, "Category")
    if cat.is_system:
        raise PermissionDeniedError("Built-in categories cannot be deleted.", code="SYSTEM_CATEGORY")
    if session.exec(select(Category.id).where(Category.parent_id == cat.id)).first():
        raise ConflictError("Delete or move the sub-categories first.", code="CATEGORY_HAS_CHILDREN")
    session.execute(sa_update(Transaction).where(Transaction.category_id == cat.id).values(category_id=None))
    session.execute(sa_update(Budget).where(Budget.category_id == cat.id).values(category_id=None))
    session.delete(cat)
    session.commit()
