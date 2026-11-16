"""Password hashing, JWT handling and the session cookie."""
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Response

from app.core.config import Settings
from app.core.timeutils import utcnow

COOKIE_NAME = "spotlight_session"
_ALGORITHM = "HS256"

_hasher = PasswordHasher()
# Verifying against this for unknown emails makes both login paths take the same time.
_DUMMY_HASH = _hasher.hash("spotlight-dummy-password")


def hash_password(password: str) -> str:
    """Hash a password with argon2."""
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Check a password against its stored hash."""
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def dummy_verify(password: str) -> None:
    """Spend the same time as a real verification, so response timing can't reveal which emails exist."""
    verify_password(_DUMMY_HASH, password)


def needs_rehash(stored_hash: str) -> bool:
    """Report whether a hash was made with weaker parameters than the current ones."""
    return _hasher.check_needs_rehash(stored_hash)


def create_token(user_id: str, settings: Settings) -> str:
    """Create a signed session token."""
    now = utcnow()
    claims = {"sub": user_id, "iat": now, "exp": now + timedelta(days=settings.jwt_expire_days)}
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=_ALGORITHM)


def decode_token(token: str, settings: Settings) -> str | None:
    """Return the user id from a valid token, or None for anything invalid or expired."""
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    return claims["sub"]


def set_session_cookie(response: Response, user_id: str, settings: Settings) -> None:
    """Attach the httpOnly session cookie."""
    response.set_cookie(
        COOKIE_NAME,
        create_token(user_id, settings),
        max_age=settings.jwt_expire_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    """Remove the session cookie."""
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax", secure=settings.cookie_secure, path="/")
