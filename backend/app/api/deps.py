"""Shared FastAPI dependencies."""
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db, is_uuid
from app.core.errors import ApiError, not_found
from app.core.logging import bind_user
from app.core.security import COOKIE_NAME, decode_token
from app.models.practice import PracticeSession
from app.models.user import User
from app.services.live.provider import LiveProvider

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    """Authenticate the session cookie. A deleted user's still-valid token fails here too."""
    token = request.cookies.get(COOKIE_NAME)
    user_id = decode_token(token, settings) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "not_authenticated", "Please log in.")
    bind_user(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_provider(request: Request) -> LiveProvider:
    """Return the app's coach backend."""
    return request.app.state.live_provider


Provider = Annotated[LiveProvider, Depends(get_provider)]


def get_owned_session(session_id: str, db: DbSession, user: CurrentUser) -> PracticeSession:
    """Load one of the user's sessions. Someone else's session looks exactly like a missing one."""
    row = db.get(PracticeSession, session_id) if is_uuid(session_id) else None
    if row is None or row.user_id != user.id:
        raise not_found("That session doesn't exist.", "session_not_found")
    return row


OwnedSession = Annotated[PracticeSession, Depends(get_owned_session)]
