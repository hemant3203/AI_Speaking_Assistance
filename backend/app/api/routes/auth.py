"""Registration, login and account management."""
from fastapi import APIRouter, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.errors import ApiError
from app.core.rate_limit import login_limiter
from app.core.security import (
    clear_session_cookie,
    dummy_verify,
    hash_password,
    needs_rehash,
    set_session_cookie,
    verify_password,
)
from app.models.gamification import Profile
from app.models.user import User
from app.schemas.auth import DeleteMeRequest, LoginRequest, RegisterRequest, UpdateMeRequest, UserEnvelope

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_rate_limit(key: str) -> None:
    if not login_limiter.hit(key):
        raise ApiError(429, "too_many_attempts", "Too many attempts. Please try again in a few minutes.")


@router.post("/register", response_model=UserEnvelope, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: DbSession, settings: AppSettings) -> dict:
    """Create an account and log it in."""
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        timezone=body.timezone,
    )
    db.add(user)
    # The unique constraint decides, not a pre-check: two simultaneous registrations could both pass one.
    try:
        db.flush()
        db.add(Profile(user_id=user.id))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists.") from exc
    set_session_cookie(response, user.id, settings)
    return {"user": user}


@router.post("/login", response_model=UserEnvelope)
def login(body: LoginRequest, request: Request, response: Response, db: DbSession, settings: AppSettings) -> dict:
    """Log in with email and password."""
    email = body.email.strip().lower()
    limiter_key = f"login:{_client_ip(request)}:{email}"
    _check_rate_limit(limiter_key)

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        dummy_verify(body.password)
        raise ApiError(401, "invalid_credentials", "Incorrect email or password.")
    if not verify_password(user.password_hash, body.password):
        raise ApiError(401, "invalid_credentials", "Incorrect email or password.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()
    login_limiter.reset(limiter_key)
    set_session_cookie(response, user.id, settings)
    return {"user": user}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: AppSettings) -> None:
    """Clear the session cookie."""
    clear_session_cookie(response, settings)


@router.get("/me", response_model=UserEnvelope)
def me(user: CurrentUser) -> dict:
    """Return the current user."""
    return {"user": user}


@router.patch("/me", response_model=UserEnvelope)
def update_me(body: UpdateMeRequest, user: CurrentUser, db: DbSession) -> dict:
    """Update the display name or timezone."""
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.timezone is not None:
        user.timezone = body.timezone
    db.commit()
    return {"user": user}


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    body: DeleteMeRequest, request: Request, response: Response, user: CurrentUser, db: DbSession, settings: AppSettings
) -> None:
    """Delete the account. Foreign keys cascade to all of the user's data."""
    # Limited like login, so a stolen cookie can't be used to guess the password here.
    _check_rate_limit(f"delete:{_client_ip(request)}:{user.id}")
    if not verify_password(user.password_hash, body.password):
        raise ApiError(401, "invalid_credentials", "Incorrect password.")
    db.delete(user)
    db.commit()
    clear_session_cookie(response, settings)
