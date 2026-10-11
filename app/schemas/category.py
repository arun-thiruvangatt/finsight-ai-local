from pydantic import BaseModel, Field

from app.core.constants import CategoryType
from app.schemas.common import ORMModel


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: int | None = None
    category_type: CategoryType = CategoryType.EXPENSE


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: int | None = None
    category_type: CategoryType | None = None


class CategoryRead(ORMModel):
    id: int
    name: str
    parent_id: int | None
    category_type: str
    is_system: bool


class CategoryTree(CategoryRead):
    children: list["CategoryTree"] = []
