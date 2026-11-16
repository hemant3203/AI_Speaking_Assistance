"""The live WebSocket endpoint: authorises the connection, then hands it to the bridge."""
import logging
from dataclasses import dataclass, replace

from fastapi import APIRouter, WebSocket
from fastapi.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.database import is_uuid, session_scope
from app.core.logging import bind_user
from app.core.security import COOKIE_NAME, decode_token
from app.models.practice import PracticeSession
from app.models.user import User
from app.services.gamification.profile import remaining_live_seconds
from app.services.live import usage
from app.services.live.bridge import CLOSE_COACH_UNAVAILABLE, BridgeSession, LiveBridge
from app.services.live.prompts import retake_slips
from app.services.live.registry import AcquireResult

router = APIRouter(tags=["live"])
logger = logging.getLogger("spotlight.live")

CLOSE_NOT_AUTHENTICATED = 4401
CLOSE_BAD_ORIGIN = 4403
CLOSE_UNKNOWN_SESSION = 4404
CLOSE_CONFLICT = 4409
CLOSE_LIMIT_REACHED = 4429


@dataclass(frozen=True)
class _Lookup:
    user_id: str | None = None
    timezone: str | None = None
    budget_seconds: float = 0.0
    session: BridgeSession | None = None
    status: str | None = None


def _look_up(user_id: str, session_id: str) -> _Lookup:
    """Load everything the connection checks need, in one short read."""
    settings = get_settings()
    with session_scope() as db:
        user = db.get(User, user_id)
        if user is None:
            return _Lookup()
        budget = remaining_live_seconds(db, user, settings)
        row = db.get(PracticeSession, session_id) if is_uuid(session_id) else None
        if row is None or row.user_id != user.id:
            return _Lookup(user_id=user.id, timezone=user.timezone, budget_seconds=budget)
        parent = db.get(PracticeSession, row.retry_of) if row.retry_of else None
        session = BridgeSession(
            session_id=row.id,
            user_id=row.user_id,
            mode=row.mode,
            topic=row.topic,
            free_talk=row.free_talk,
            language=row.language,
            coach_id=row.coach_id,
            target_seconds=row.target_seconds,
            local_date=row.local_date,
            retake_slips=retake_slips(parent.feedback) if parent is not None and parent.user_id == row.user_id else None,
        )
        return _Lookup(user.id, user.timezone, budget, session, row.status)


@router.websocket("/live/{session_id}")
async def live(websocket: WebSocket, session_id: str) -> None:
    """Run one live coaching session."""
    settings = get_settings()
    # Always accept first. If the handshake were refused, the browser would only ever see a generic
    # failure and never the close code. Nothing is read or sent before these checks pass.
    await websocket.accept()

    if websocket.headers.get("origin") not in settings.origin_list:
        await websocket.close(CLOSE_BAD_ORIGIN)
        return

    token = websocket.cookies.get(COOKIE_NAME)
    token_user_id = decode_token(token, settings) if token else None
    if token_user_id is None:
        await websocket.close(CLOSE_NOT_AUTHENTICATED)
        return

    lookup = await run_in_threadpool(_look_up, token_user_id, session_id)
    if lookup.user_id is None:
        await websocket.close(CLOSE_NOT_AUTHENTICATED)
        return
    bind_user(lookup.user_id)

    if lookup.session is None:
        await websocket.close(CLOSE_UNKNOWN_SESSION)
        return
    if lookup.status != "created":
        await websocket.close(CLOSE_CONFLICT)
        return

    provider = websocket.app.state.live_provider
    if not provider.is_available():
        await websocket.close(CLOSE_COACH_UNAVAILABLE)
        return
    if lookup.budget_seconds <= 0:
        await websocket.close(CLOSE_LIMIT_REACHED)
        return

    registry = websocket.app.state.live_registry
    slot = registry.acquire(lookup.user_id)
    if slot is AcquireResult.USER_BUSY:
        await websocket.close(CLOSE_CONFLICT)
        return
    if slot is AcquireResult.FULL:
        logger.warning("live capacity reached, refusing a connection")
        await websocket.close(CLOSE_LIMIT_REACHED)
        return

    try:
        today = await run_in_threadpool(usage.claim_session, session_id, lookup.user_id, lookup.timezone)
        if today is None:
            await websocket.close(CLOSE_CONFLICT)
            return
        session = replace(lookup.session, local_date=today)
        await LiveBridge(websocket, session, provider, settings, lookup.budget_seconds).run()
    finally:
        registry.release(lookup.user_id)
