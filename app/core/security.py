import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError


def _prepare(password: str) -> bytes:
    # bcrypt only reads 72 bytes; pre-hash so long passwords are not silently truncated.
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode())
    except ValueError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _encode(payload: dict) -> str:
    s = get_settings()
    return jwt.encode(payload, s.JWT_SECRET_KEY, algorithm=s.JWT_ALGORITHM)


def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    now = datetime.now(UTC)
    return _encode({
        "sub": str(user_id), "role": role, "type": "access",
        "iat": now, "exp": now + timedelta(minutes=s.ACCESS_TOKEN_EXPIRE_MINUTES),
    })


def create_refresh_token(user_id: int) -> tuple[str, str, datetime]:
    """Returns (token, jti, expires_at)."""
    s = get_settings()
    now = datetime.now(UTC)
    jti = uuid.uuid4().hex
    exp = now + timedelta(days=s.REFRESH_TOKEN_EXPIRE_DAYS)
    return _encode({"sub": str(user_id), "type": "refresh", "jti": jti, "iat": now, "exp": exp}), jti, exp


def decode_token(token: str, expected_type: str) -> dict:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.JWT_SECRET_KEY, algorithms=[s.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired.", code="TOKEN_EXPIRED") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid token.", code="INVALID_TOKEN") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("Wrong token type.", code="INVALID_TOKEN")
    return payload
