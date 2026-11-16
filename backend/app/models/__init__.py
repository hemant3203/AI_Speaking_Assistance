"""Imports every model, so that Base.metadata is complete for Alembic and the tests."""
from app.models.gamification import (
    DailyActivity,
    LedgerEntry,
    OwnedItem,
    Profile,
    QuestCompletion,
    StreakDay,
    UserBadge,
)
from app.models.practice import PracticeSession
from app.models.user import User

__all__ = [
    "DailyActivity",
    "LedgerEntry",
    "OwnedItem",
    "PracticeSession",
    "Profile",
    "QuestCompletion",
    "StreakDay",
    "User",
    "UserBadge",
]
