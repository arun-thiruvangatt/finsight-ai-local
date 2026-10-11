from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.category import CategoryCreate, CategoryRead, CategoryTree, CategoryUpdate
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.post("", response_model=CategoryRead, status_code=201, summary="Create category")
def create_category(data: CategoryCreate, user: CurrentUser, session: SessionDep):
    return category_service.create(session, user.id, data)


@router.get("", response_model=list[CategoryRead], summary="List categories (flat)")
def list_categories(user: CurrentUser, session: SessionDep):
    return category_service.list_categories(session, user.id)


@router.get("/tree", response_model=list[CategoryTree], summary="Category hierarchy")
def category_tree(user: CurrentUser, session: SessionDep):
    return category_service.get_tree(session, user.id)


@router.patch("/{category_id}", response_model=CategoryRead, summary="Update category")
def update_category(category_id: int, data: CategoryUpdate, user: CurrentUser, session: SessionDep):
    return category_service.update(session, user.id, category_id, data)


@router.delete("/{category_id}", status_code=204, summary="Delete category")
def delete_category(category_id: int, user: CurrentUser, session: SessionDep):
    category_service.delete(session, user.id, category_id)
    return Response(status_code=204)
