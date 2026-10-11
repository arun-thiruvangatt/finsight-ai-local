from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_session

bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token from /auth/login")

SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(request: Request, session: SessionDep,
                     creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> User:
    if creds is None:
        raise AuthenticationError("Not authenticated.", code="NOT_AUTHENTICATED")
    payload = decode_token(creds.credentials, "access")
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or disabled.", code="INVALID_TOKEN")
    request.state.user_id = user.id  # read by the logging middleware
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: str):
    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError("You do not have permission to do this.")
        return user
    return checker


def rate_limit(bucket: str, limit_attr: str):
    """Per-user limiter for expensive endpoints; limit comes from settings (e.g. RATE_LIMIT_AI_PER_MINUTE)."""
    def dep(user: CurrentUser) -> None:
        enforce_rate_limit(f"{bucket}:{user.id}", getattr(get_settings(), limit_attr))
    return dep
