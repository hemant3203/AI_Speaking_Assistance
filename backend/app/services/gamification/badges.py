"""Badge definitions and progress, computed from a user's lifetime counters."""
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.services.catalog import MODES
from app.services.gamification.xp import level_for_xp


@dataclass(frozen=True)
class BadgeDefinition:
    """One badge that can be earned."""

    id: str
    name: str
    description: str
    icon: str
    category: str
    tier: str
    target: int
    xp: int
    sparks: int
    progress: Callable[[Any], float]


def _streak(profile: Any) -> int:
    return profile.streak_longest


def _sessions(profile: Any) -> int:
    return profile.total_sessions


def _minutes(profile: Any) -> float:
    return profile.total_speaking_seconds / 60


def _best_score(profile: Any) -> int:
    return profile.best_score or 0


def _level(profile: Any) -> int:
    return level_for_xp(profile.xp)


BADGES = [
    BadgeDefinition("streak_3", "Getting Warm", "Reach a 3-day streak", "Flame", "streak", "bronze", 3, 15, 5, _streak),
    BadgeDefinition("streak_7", "Week Strong", "Reach a 7-day streak", "Flame", "streak", "silver", 7, 30, 10, _streak),
    BadgeDefinition("streak_30", "Monthly Habit", "Reach a 30-day streak", "Flame", "streak", "gold", 30, 100, 25, _streak),
    BadgeDefinition("streak_100", "Unstoppable", "Reach a 100-day streak", "Crown", "streak", "gold", 100, 300, 50, _streak),
    BadgeDefinition("sessions_1", "First Words", "Finish your first session", "Mic", "volume", "bronze", 1, 10, 5, _sessions),
    BadgeDefinition("sessions_10", "Regular", "Finish 10 sessions", "Mic", "volume", "silver", 10, 40, 10, _sessions),
    BadgeDefinition("sessions_50", "Seasoned", "Finish 50 sessions", "Mic", "volume", "gold", 50, 120, 25, _sessions),
    BadgeDefinition("minutes_60", "An Hour on Stage", "Speak for 60 minutes in total", "Clock", "volume", "silver", 60, 50, 10, _minutes),
    BadgeDefinition("minutes_300", "Marathon Talker", "Speak for 300 minutes in total", "Clock", "volume", "gold", 300, 150, 30, _minutes),
    BadgeDefinition("score_80", "Crowd Favourite", "Score at least 80", "Star", "skill", "silver", 80, 40, 10, _best_score),
    BadgeDefinition("score_90", "Standing Ovation", "Score at least 90", "Trophy", "skill", "gold", 90, 80, 20, _best_score),
    BadgeDefinition(
        "clean_speaker", "Clean Speaker", "Finish a session with under 1 filler per 100 words", "Sparkles",
        "skill", "silver", 1, 40, 10, lambda p: p.clean_sessions,
    ),
    BadgeDefinition(
        "pace_setter", "Pace Setter", "Stay in the 120-160 WPM band in 5 sessions", "Gauge", "skill", "silver",
        5, 40, 10, lambda p: p.pace_in_band_sessions,
    ),
    BadgeDefinition(
        "all_modes", "All-Rounder", "Practise every mode", "Shapes", "variety", "silver", len(MODES), 50, 15,
        lambda p: len(p.modes_practised),
    ),
    BadgeDefinition(
        "challenge_1", "Challenge Accepted", "Complete a daily challenge", "Swords", "challenge", "bronze",
        1, 15, 5, lambda p: p.challenges_completed,
    ),
    BadgeDefinition(
        "challenge_10", "Challenge Champion", "Complete 10 daily challenges", "Medal", "challenge", "gold",
        10, 100, 25, lambda p: p.challenges_completed,
    ),
    BadgeDefinition(
        "comeback_1", "Comeback Kid", "Beat your own score with a second take", "RotateCcw", "challenge",
        "bronze", 1, 15, 5, lambda p: p.comebacks,
    ),
    BadgeDefinition(
        "comeback_10", "Never Settles", "Win 10 comeback bonuses", "TrendingUp", "challenge", "silver",
        10, 50, 15, lambda p: p.comebacks,
    ),
    BadgeDefinition("level_5", "Rising Voice", "Reach level 5", "TrendingUp", "level", "silver", 5, 30, 10, _level),
    BadgeDefinition("level_10", "Spotlight Legend", "Reach level 10", "Award", "level", "gold", 10, 100, 25, _level),
]
BADGES_BY_ID = {badge.id: badge for badge in BADGES}


def badge_view(badge: BadgeDefinition, profile: Any, unlocked_at: datetime | None) -> dict[str, Any]:
    """Return a badge as the API shows it. Progress is capped so the UI never shows 120 of 100."""
    return {
        "id": badge.id,
        "name": badge.name,
        "description": badge.description,
        "icon": badge.icon,
        "category": badge.category,
        "tier": badge.tier,
        "target": badge.target,
        "progress": min(badge.target, int(badge.progress(profile))),
        "unlocked": unlocked_at is not None,
        "unlocked_at": unlocked_at,
        "xp": badge.xp,
        "sparks": badge.sparks,
    }


def newly_earned(profile: Any, unlocked_ids: set[str]) -> list[BadgeDefinition]:
    """Return the badges a profile now qualifies for but hasn't unlocked yet."""
    return [
        badge for badge in BADGES if badge.id not in unlocked_ids and badge.progress(profile) >= badge.target
    ]


def all_badge_views(profile: Any, unlocked: dict[str, datetime]) -> list[dict[str, Any]]:
    """Return every badge with the user's progress."""
    return [badge_view(badge, profile, unlocked.get(badge.id)) for badge in BADGES]


def next_badge_view(profile: Any, unlocked: dict[str, datetime]) -> dict[str, Any] | None:
    """Return the locked badge the user is closest to, or None when all are unlocked."""
    locked = [badge for badge in BADGES if badge.id not in unlocked]
    if not locked:
        return None
    closest = max(locked, key=lambda badge: min(1.0, badge.progress(profile) / badge.target))
    return badge_view(closest, profile, None)
