"""Database operations for the live session lifecycle. All are sync, and called through the thread pool."""
from datetime import date

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert

from app.core.database import session_scope
from app.core.timeutils import local_date, utcnow
from app.models.gamification import DailyActivity
from app.models.practice import PracticeSession
from app.models.user import lock_user


def claim_session(session_id: str, user_id: str, timezone: str) -> date | None:
    """Move a session from created to active. Returns its local date, or None if it was already claimed.

    The status check is part of the UPDATE, so two sockets racing for one session can't both win.
    """
    now = utcnow()
    today = local_date(timezone, now)
    with session_scope() as db:
        claimed = db.scalar(
            update(PracticeSession)
            .where(
                PracticeSession.id == session_id,
                PracticeSession.user_id == user_id,
                PracticeSession.status == "created",
            )
            .values(status="active", started_at=now, local_date=today)
            .returning(PracticeSession.id)
        )
    return today if claimed else None


def close_session(
    session_id: str, user_id: str, day: date, live_seconds: float, coach_transcript: str, abandon: bool
) -> None:
    """Record what a closed connection used, and abandon the session if the speech never ended."""
    with session_scope() as db:
        # Takes the user lock first, like every multi-row writer. See lock_user for why.
        if lock_user(db, user_id) is None:
            return
        db.execute(
            insert(DailyActivity)
            .values(user_id=user_id, local_date=day, live_seconds=live_seconds)
            .on_conflict_do_update(
                index_elements=[DailyActivity.user_id, DailyActivity.local_date],
                set_={"live_seconds": DailyActivity.live_seconds + live_seconds},
            )
        )
        db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == session_id)
            .values(live_seconds=live_seconds, coach_transcript=coach_transcript)
        )
        if abandon:
            db.execute(
                update(PracticeSession)
                .where(PracticeSession.id == session_id, PracticeSession.status == "active")
                .values(status="abandoned", ended_at=utcnow())
            )


def abandon_session(session_id: str) -> None:
    """Abandon an active session whose scoring failed outright."""
    with session_scope() as db:
        db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == session_id, PracticeSession.status == "active")
            .values(status="abandoned", ended_at=utcnow())
        )


def abandon_stale_sessions() -> int:
    """Abandon sessions left active by a previous process. Returns how many there were."""
    with session_scope() as db:
        result = db.execute(
            update(PracticeSession)
            .where(PracticeSession.status == "active")
            .values(status="abandoned", ended_at=utcnow())
        )
        return result.rowcount
