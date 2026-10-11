from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, SessionDep
from app.core.rate_limit import enforce_rate_limit
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.common import ErrorResponse, Message
from app.schemas.user import UserRead
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=201, summary="Create an account",
             responses={409: {"model": ErrorResponse}})
def register(data: RegisterRequest, session: SessionDep):
    return auth_service.register(session, data)


@router.post("/login", response_model=TokenResponse, summary="Exchange credentials for tokens",
             responses={401: {"model": ErrorResponse}})
def login(data: LoginRequest, request: Request, session: SessionDep):
    ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"login:{ip}:{data.email.lower()}", 10)  # brute-force protection
    user = auth_service.authenticate(session, data.email, data.password)
    return auth_service.issue_tokens(session, user)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate refresh token, get new access token")
def refresh(data: RefreshRequest, session: SessionDep):
    return auth_service.refresh(session, data.refresh_token)


@router.post("/logout", response_model=Message, summary="Revoke a refresh token")
def logout(data: RefreshRequest, session: SessionDep):
    auth_service.logout(session, data.refresh_token)
    return Message(message="Logged out.")


@router.get("/me", response_model=UserRead, summary="Current user")
def me(user: CurrentUser):
    return user
