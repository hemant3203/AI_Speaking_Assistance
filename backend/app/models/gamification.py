"""The gamification aggregate: wallet, streak, daily progress, badges, purchases and the ledger.

Lifetime numbers live here rather than being derived from sessions, because deleting a session must
not take away XP, badges or a streak that were already earned.
"""
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutils import utcnow


def _user_fk() -> ForeignKey:
    return ForeignKey("users.id", ondelete="CASCADE")


class Profile(Base):
    """A user's wallet, streak state and lifetime counters."""

    __tablename__ = "profiles"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    sparks: Mapped[int] = mapped_column(Integer, default=0)
    streak_current: Mapped[int] = mapped_column(Integer, default=0)
    streak_longest: Mapped[int] = mapped_column(Integer, default=0)
    last_practice_date: Mapped[date | None] = mapped_column(Date)
    freezes: Mapped[int] = mapped_column(Integer, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0)
    total_speaking_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    best_score: Mapped[int | None] = mapped_column(Integer)
    clean_sessions: Mapped[int] = mapped_column(Integer, default=0)
    pace_in_band_sessions: Mapped[int] = mapped_column(Integer, default=0)
    modes_practised: Mapped[list] = mapped_column(JSONB, default=list)
    challenges_completed: Mapped[int] = mapped_column(Integer, default=0)
    comebacks: Mapped[int] = mapped_column(Integer, default=0)


class StreakDay(Base):
    """One local day that a streak covered, either practised or frozen."""

    __tablename__ = "streak_days"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    state: Mapped[str] = mapped_column(String(16))


class DailyActivity(Base):
    """One user's progress on one local day, the input for quests and the daily cost guard."""

    __tablename__ = "daily_activity"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    speaking_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    # Kept here, not summed from sessions, so deleting a session doesn't refund the shared-key budget.
    live_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    best_score: Mapped[int] = mapped_column(Integer, default=0)
    low_filler_done: Mapped[bool] = mapped_column(Boolean, default=False)
    on_pace_done: Mapped[bool] = mapped_column(Boolean, default=False)
    modes: Mapped[list] = mapped_column(JSONB, default=list)
    # Comeback bonuses paid today, against comebacks.DAILY_LIMIT.
    comebacks: Mapped[int] = mapped_column(Integer, default=0)


class QuestCompletion(Base):
    """A completed daily quest. The primary key allows each quest to complete once per user per day."""

    __tablename__ = "quest_completions"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    local_date: Mapped[date] = mapped_column(Date, primary_key=True)
    quest_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserBadge(Base):
    """An unlocked badge. The primary key allows each badge to unlock once per user."""

    __tablename__ = "user_badges"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    badge_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OwnedItem(Base):
    """A permanent shop purchase such as a coach. Consumables are counted on the profile instead."""

    __tablename__ = "owned_items"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk(), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerEntry(Base):
    """An audit line for each XP or sparks change, and the database's guard against double rewards.

    `dedupe_key` names what was rewarded (`session:<id>`, `badge:<id>`, `quest:<date>:<id>`). Purchases
    leave it null because a consumable can be bought repeatedly, and Postgres treats nulls as distinct.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_ledger_entries_user_dedupe_key"),
        Index("ix_ledger_entries_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), _user_fk())
    # SET NULL because rewards must outlive a deleted session.
    session_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("practice_sessions.id", ondelete="SET NULL"), index=True
    )
    dedupe_key: Mapped[str | None] = mapped_column(String(96))
    reason: Mapped[str] = mapped_column(String(120))
    xp: Mapped[int] = mapped_column(Integer, default=0)
    sparks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
