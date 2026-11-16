"""Builds the gamification profile, which draws on most of the other gamification modules."""
import math
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.timeutils import local_date
from app.models.gamification import DailyActivity, LedgerEntry, Profile, QuestCompletion, StreakDay, UserBadge
from app.models.practice import PracticeSession
from app.models.user import User
from app.services.catalog import MODES
from app.services.gamification import badges, challenges, quests, streaks, xp

_RECENT_BADGE_COUNT = 3
_WEEK_LOOKBACK_DAYS = 6


def unlocked_badges(db: Session, user_id: str) -> dict[str, datetime]:
    """Return unlock times by badge id."""
    rows = db.execute(select(UserBadge.badge_id, UserBadge.unlocked_at).where(UserBadge.user_id == user_id))
    return dict(rows.tuples().all())


def used_live_seconds(db: Session, user_id: str, day: Any) -> float:
    """Return the live time a user has used on a local day."""
    used = db.scalar(
        select(DailyActivity.live_seconds).where(DailyActivity.user_id == user_id, DailyActivity.local_date == day)
    )
    return used or 0.0


def remaining_live_seconds(db: Session, user: User, settings: Settings, now: datetime | None = None) -> float:
    """Return what is left of today's live-time budget. The admin has no daily budget."""
    if user.is_admin:
        return math.inf
    used = used_live_seconds(db, user.id, local_date(user.timezone, now))
    return max(0.0, settings.daily_live_seconds_per_user - used)


def daily_challenge(db: Session, user_id: str, day: date, total_completed: int) -> dict[str, Any]:
    """Return a day's challenge, and whether this user has completed it."""
    claim = db.execute(
        select(LedgerEntry.session_id).where(
            LedgerEntry.user_id == user_id, LedgerEntry.dedupe_key == challenges.dedupe_key(day)
        )
    ).first()
    session_id = claim.session_id if claim else None
    # The session may have been deleted since, which keeps the completion but loses its score.
    score = db.scalar(select(PracticeSession.overall_score).where(PracticeSession.id == session_id)) if session_id else None
    mode = challenges.challenge_for(day).mode
    mode_name = next((item["name"] for item in MODES if item["id"] == mode), mode)
    return challenges.challenge_view(day, mode_name, session_id, score, claim is not None, total_completed)


def build_profile(db: Session, user: User, settings: Settings, now: datetime | None = None) -> dict[str, Any]:
    """Return the body of GET /gamification/profile."""
    today = local_date(user.timezone, now)
    profile = db.get(Profile, user.id)
    progress = xp.level_progress(profile.xp)

    status = streaks.read_status(today, profile.last_practice_date, profile.streak_current, profile.freezes)
    day_states = dict(
        db.execute(
            select(StreakDay.local_date, StreakDay.state).where(
                StreakDay.user_id == user.id, StreakDay.local_date >= today - timedelta(days=_WEEK_LOOKBACK_DAYS)
            )
        ).tuples().all()
    )

    activity = db.get(DailyActivity, (user.id, today))
    completed_ids = set(
        db.scalars(
            select(QuestCompletion.quest_id).where(
                QuestCompletion.user_id == user.id, QuestCompletion.local_date == today
            )
        )
    )
    quest_items = quests.daily_quest_items(user.id, today, activity, completed_ids)

    unlocked = unlocked_badges(db, user.id)
    recent_ids = sorted(unlocked, key=unlocked.__getitem__, reverse=True)[:_RECENT_BADGE_COUNT]
    used = activity.live_seconds if activity else 0.0
    budget = settings.daily_live_seconds_per_user

    return {
        "xp": profile.xp,
        "level": progress.level,
        "level_title": progress.title,
        "xp_into_level": progress.xp_into_level,
        "xp_for_next_level": progress.xp_for_next_level,
        "sparks": profile.sparks,
        "streak": {
            "current": status.current,
            "longest": profile.streak_longest,
            "status": status.status,
            "freezes": profile.freezes,
            "practiced_today": status.practiced_today,
            "next_milestone": streaks.next_milestone(status.current),
            "week": streaks.week_view(today, day_states),
        },
        "daily_quests": {
            "date": today.isoformat(),
            "all_complete": all(item["completed"] for item in quest_items),
            "bonus_sparks": quests.BONUS_SPARKS,
            "items": quest_items,
        },
        "stats": {
            "total_sessions": profile.total_sessions,
            "total_speaking_seconds": round(profile.total_speaking_seconds),
            "best_score": profile.best_score,
        },
        "recent_badges": [
            badges.badge_view(badges.BADGES_BY_ID[badge_id], profile, unlocked[badge_id]) for badge_id in recent_ids
        ],
        "next_badge": badges.next_badge_view(profile, unlocked),
        "limits": {
            "daily_live_seconds": budget,
            "used_seconds": round(used),
            "remaining_seconds": budget if user.is_admin else max(0, round(budget - used)),
            "unlimited": user.is_admin,
        },
        "daily_challenge": daily_challenge(db, user.id, today, profile.challenges_completed),
    }
