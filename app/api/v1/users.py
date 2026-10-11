from fastapi import APIRouter, Depends
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, require_role
from app.db.models import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead, summary="Get my profile")
def get_me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserRead, summary="Update my profile")
def update_me(data: UserUpdate, user: CurrentUser, session: SessionDep):
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.get("", response_model=list[UserRead], summary="List all users (ADMIN only)",
            dependencies=[Depends(require_role("ADMIN"))])
def list_users(session: SessionDep):
    return session.exec(select(User).order_by(User.id).limit(200)).all()
