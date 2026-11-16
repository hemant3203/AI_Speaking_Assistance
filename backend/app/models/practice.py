"""The practice session aggregate."""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.database import Base
from app.core.timeutils import utcnow


class PracticeSession(Base):
    """One attempt at a speech, from creation through scoring."""

    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index("ix_practice_sessions_user_local_date", "user_id", "local_date"),
        Index("ix_practice_sessions_user_status_started", "user_id", "status", "started_at"),
        Index("ix_practice_sessions_status", "status"),
        Index("ix_practice_sessions_retry_of", "retry_of"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(32))
    topic: Mapped[str] = mapped_column(String(200))
    # The speaker chose their own subject. `topic` starts as "Free talk" and gains the subject once scored.
    free_talk: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    language: Mapped[str] = mapped_column(String(16))
    coach_id: Mapped[str] = mapped_column(String(32))
    target_seconds: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="created")
    # A second take of an earlier session, which it tries to beat for a comeback bonus.
    retry_of: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("practice_sessions.id", ondelete="SET NULL")
    )
    # Set when the session takes on that day's challenge.
    challenge_date: Mapped[date | None] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    local_date: Mapped[date] = mapped_column(Date)

    speaking_seconds: Mapped[float | None] = mapped_column(Float)
    # Counts toward the daily cost guard: the larger of the connected time and the audio received.
    live_seconds: Mapped[float] = mapped_column(Float, default=0.0)

    word_count: Mapped[int | None] = mapped_column(Integer)
    wpm: Mapped[float | None] = mapped_column(Float)
    filler_count: Mapped[int | None] = mapped_column(Integer)
    filler_per_100: Mapped[float | None] = mapped_column(Float)
    filler_breakdown: Mapped[dict | None] = mapped_column(JSONB)
    hedge_count: Mapped[int | None] = mapped_column(Integer)
    pause_count: Mapped[int | None] = mapped_column(Integer)
    longest_pause_seconds: Mapped[float | None] = mapped_column(Float)
    pause_ratio: Mapped[float | None] = mapped_column(Float)
    volume_variation: Mapped[float | None] = mapped_column(Float)
    vocabulary_ratio: Mapped[float | None] = mapped_column(Float)

    scores: Mapped[dict | None] = mapped_column(JSONB)
    overall_score: Mapped[int | None] = mapped_column(Integer)
    ai_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    # Models disagree on subjective scores, so this explains jumps in a user's trend.
    analysis_model: Mapped[str | None] = mapped_column(String(64))
    filler_counts_reliable: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[dict | None] = mapped_column(JSONB)

    # Deferred because list and analytics queries load many rows and never read the text.
    transcript: Mapped[str | None] = deferred(mapped_column(Text))
    coach_transcript: Mapped[str | None] = deferred(mapped_column(Text))

    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    sparks_awarded: Mapped[int] = mapped_column(Integer, default=0)
    # Set once by the reward transaction, and returned as-is if finalisation ever runs again.
    result_payload: Mapped[dict | None] = deferred(mapped_column(JSONB))
    finalised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
