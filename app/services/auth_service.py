from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, PermissionDeniedError
from app.core.security import (create_access_token, create_refresh_token, decode_token, hash_password,
                               hash_token, verify_password)
from app.db.models import AuditLog, RefreshToken, User
from app.schemas.auth import RegisterRequest
from app.services import category_service


def audit(session: Session, user_id: int | None, action: str, entity: str | None = None,
          entity_id: object | None = None, meta: dict | None = None) -> None:
    session.add(AuditLog(user_id=user_id, action=action, entity=entity,
                         entity_id=str(entity_id) if entity_id is not None else None, meta=meta or {}))


def register(session: Session, data: RegisterRequest) -> User:
    email = data.email.lower()
    if session.exec(select(User).where(User.email == email)).first():
        raise ConflictError("An account with this email already exists.", code="EMAIL_ALREADY_REGISTERED")
    user = User(email=email, password_hash=hash_password(data.password), full_name=data.full_name.strip())
    session.add(user)
    session.flush()
    category_service.ensure_default_categories(session, user.id)
    audit(session, user.id, "user.register", "user", user.id)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.exec(select(User).where(User.email == email.lower())).first()
    # Always run a hash comparison to keep timing similar for unknown emails.
    valid = verify_password(password, user.password_hash if user else hash_password("dummy-password"))
    if not user or not valid:
        raise AuthenticationError("Invalid email or password.", code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise PermissionDeniedError("This account is disabled.", code="ACCOUNT_DISABLED")
    audit(session, user.id, "user.login", "user", user.id)
    session.commit()
    return user


def issue_tokens(session: Session, user: User) -> dict:
    refresh, jti, exp = create_refresh_token(user.id)
    session.add(RefreshToken(user_id=user.id, jti=jti, token_hash=hash_token(refresh), expires_at=exp))
    session.commit()
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


def _revoke_all(session: Session, user_id: int) -> None:
    for rt in session.exec(select(RefreshToken).where(RefreshToken.user_id == user_id,
                                                      RefreshToken.revoked == False)):  # noqa: E712
        rt.revoked = True
        session.add(rt)


def refresh(session: Session, refresh_token: str) -> dict:
    payload = decode_token(refresh_token, "refresh")
    stored = session.exec(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).first()
    if not stored or stored.token_hash != hash_token(refresh_token):
        raise AuthenticationError("Invalid refresh token.", code="INVALID_TOKEN")
    if stored.revoked:
        # Reuse of a rotated token => assume theft, kill every session of this user.
        _revoke_all(session, stored.user_id)
        session.commit()
        raise AuthenticationError("Refresh token was already used.", code="TOKEN_REUSED")
    if stored.expires_at <= datetime.now(UTC):
        raise AuthenticationError("Refresh token expired.", code="TOKEN_EXPIRED")
    user = session.get(User, stored.user_id)
    if not user or not user.is_active:
        raise AuthenticationError("User not available.", code="INVALID_TOKEN")
    stored.revoked = True
    session.add(stored)
    return issue_tokens(session, user)


def logout(session: Session, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except AuthenticationError:
        return  # logging out with a dead token is a no-op
    stored = session.exec(select(RefreshToken).where(RefreshToken.jti == payload["jti"])).first()
    if stored and not stored.revoked:
        stored.revoked = True
        session.add(stored)
        audit(session, stored.user_id, "user.logout", "user", stored.user_id)
        session.commit()
