"""Practice catalog and sessions."""
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.deps import AppSettings, CurrentUser, DbSession, OwnedSession, Provider
from app.core.errors import ApiError
from app.core.timeutils import local_date
from app.models.practice import PracticeSession
from app.models.user import lock_user
from app.schemas.practice import (
    CatalogOut,
    CreateSessionRequest,
    ModeId,
    SessionDetail,
    SessionList,
    SessionSummary,
)
from app.services.catalog import DURATIONS, FREE_TALK_TOPIC, LANGUAGES, MODES
from app.services.gamification import challenges
from app.services.gamification.profile import remaining_live_seconds

router = APIRouter(prefix="/practice", tags=["practice"])

_HIDDEN_STATUSES = ("created", "abandoned")


@router.get("/catalog", response_model=CatalogOut)
def catalog(_: CurrentUser) -> dict:
    """Return the modes, topics, durations and languages."""
    return {"modes": MODES, "durations": DURATIONS, "languages": LANGUAGES}


@router.post("/sessions", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(
    body: CreateSessionRequest, user: CurrentUser, db: DbSession, settings: AppSettings, provider: Provider
) -> SessionDetail:
    """Create a session, ready for the live WebSocket to connect to."""
    if not provider.is_available():
        raise ApiError(503, "coach_unavailable", "The coach isn't available right now.")
    if remaining_live_seconds(db, user, settings) <= 0:
        raise ApiError(429, "daily_limit_reached", "You've used today's practice time. Come back tomorrow.")

    today = local_date(user.timezone)
    mode, topic, free_talk, language = body.mode, body.topic, body.free_talk, body.language
    retry_of = challenge_date = None
    if body.retry_of is not None:
        # A second take repeats the first exactly, so the comparison between them is fair.
        parent = db.get(PracticeSession, str(body.retry_of))
        if parent is None or parent.user_id != user.id or parent.status != "completed":
            raise ApiError(404, "session_not_found", "We can't find the take you want to beat.")
        retry_of, mode, language, free_talk = parent.id, parent.mode, parent.language, parent.free_talk
        topic = FREE_TALK_TOPIC if parent.free_talk else parent.topic
        if parent.challenge_date == today and body.target_seconds in challenges.LENGTHS:
            challenge_date = today
    elif body.challenge:
        challenge = challenges.challenge_for(today)
        mode, topic, free_talk, challenge_date = challenge.mode, challenge.topic_for(language), False, today

    row = PracticeSession(
        user_id=user.id,
        mode=mode,
        topic=topic,
        free_talk=free_talk,
        language=language,
        coach_id=user.equipped_coach,
        target_seconds=body.target_seconds,
        local_date=today,
        retry_of=retry_of,
        challenge_date=challenge_date,
    )
    db.add(row)
    db.commit()
    return SessionDetail.from_row(row)


@router.get("/sessions", response_model=SessionList)
def list_sessions(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    mode: ModeId | None = None,
) -> SessionList:
    """List finished sessions, newest first."""
    conditions = [PracticeSession.user_id == user.id, PracticeSession.status.not_in(_HIDDEN_STATUSES)]
    if mode is not None:
        conditions.append(PracticeSession.mode == mode)
    total = db.scalar(select(func.count()).select_from(PracticeSession).where(*conditions))
    rows = db.scalars(
        select(PracticeSession)
        .where(*conditions)
        .order_by(PracticeSession.started_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return SessionList(items=[SessionSummary.from_row(row) for row in rows], total=total)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(row: OwnedSession) -> SessionDetail:
    """Return one session in full."""
    return SessionDetail.from_row(row)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(row: OwnedSession, db: DbSession) -> None:
    """Delete a session and its transcripts. XP and badges already earned are kept."""
    # Follows the lock order in lock_user, since the delete also touches ledger rows.
    lock_user(db, row.user_id)
    db.delete(row)
    db.commit()
