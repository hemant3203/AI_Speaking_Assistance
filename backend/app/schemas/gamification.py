"""Response models for gamification."""
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import UtcDatetime


class Badge(BaseModel):
    """A badge with the user's progress."""

    id: str
    name: str
    description: str
    icon: str
    category: str
    tier: Literal["bronze", "silver", "gold"]
    target: int
    progress: int
    unlocked: bool
    unlocked_at: UtcDatetime | None
    xp: int
    sparks: int


class BadgeList(BaseModel):
    """Body of GET /gamification/badges."""

    items: list[Badge]


class Quest(BaseModel):
    """A daily quest with the user's progress."""

    id: str
    title: str
    description: str
    icon: str
    progress: int
    target: int
    xp: int
    sparks: int
    completed: bool


class WeekDay(BaseModel):
    """One day in the streak's week strip."""

    date: str
    state: Literal["practiced", "frozen", "missed", "today_pending"]


class StreakView(BaseModel):
    """The streak as shown on the profile."""

    current: int
    longest: int
    status: Literal["active_today", "at_risk", "none"]
    freezes: int
    practiced_today: bool
    next_milestone: int
    week: list[WeekDay]


class DailyQuests(BaseModel):
    """Today's quests."""

    date: str
    all_complete: bool
    bonus_sparks: int
    items: list[Quest]


class ProfileStats(BaseModel):
    """Lifetime totals."""

    total_sessions: int
    total_speaking_seconds: int
    best_score: int | None


class Limits(BaseModel):
    """The daily live-time budget."""

    daily_live_seconds: int
    used_seconds: int
    remaining_seconds: int
    unlimited: bool


class ChallengeOption(BaseModel):
    """One length the daily challenge can be taken at, and what completing it pays."""

    target_seconds: int
    min_seconds: int
    xp: int
    sparks: int


class DailyChallenge(BaseModel):
    """Today's challenge topic, the same for everyone."""

    date: str
    mode: str
    mode_name: str
    topic: str
    topic_hi: str
    options: list[ChallengeOption]
    completed: bool
    session_id: str | None
    score: int | None
    total_completed: int


class ProfileOut(BaseModel):
    """Body of GET /gamification/profile."""

    xp: int
    level: int
    level_title: str
    xp_into_level: int
    xp_for_next_level: int
    sparks: int
    streak: StreakView
    daily_quests: DailyQuests
    stats: ProfileStats
    recent_badges: list[Badge]
    next_badge: Badge | None
    limits: Limits
    daily_challenge: DailyChallenge


class ShopItem(BaseModel):
    """One item in the shop."""

    id: str
    kind: Literal["consumable", "coach"]
    name: str
    description: str
    price: int
    icon: str
    owned: bool
    equipped: bool
    can_buy: bool
    reason: str | None


class ShopOut(BaseModel):
    """Body of GET /gamification/shop."""

    sparks: int
    items: list[ShopItem]


class PurchaseOut(BaseModel):
    """Body of POST /gamification/shop/{item_id}/purchase."""

    sparks: int
    item: ShopItem


class ActivityItem(BaseModel):
    """One line of the reward ledger."""

    created_at: UtcDatetime
    reason: str
    xp: int
    sparks: int


class ActivityOut(BaseModel):
    """Body of GET /gamification/activity."""

    items: list[ActivityItem]


class XpLine(BaseModel):
    """One line of an XP breakdown."""

    label: str
    xp: int


class RewardStreak(BaseModel):
    """What a session did to the streak."""

    current: int
    longest: int
    extended: bool
    freeze_used: int
    freeze_earned: bool


class ComebackReward(BaseModel):
    """How a second take compared with the take it tried to beat.

    `reason` says why no bonus was paid: `not_improved`, `already_claimed` or `daily_limit`.
    """

    parent_id: str
    score_before: int
    score_after: int
    grammar_before: int | None
    grammar_after: int | None
    slips_before: int | None
    slips_after: int | None
    improved: bool
    xp: int
    sparks: int
    reason: Literal["not_improved", "already_claimed", "daily_limit"] | None


class ChallengeReward(BaseModel):
    """What a daily challenge attempt achieved. `reason` is `too_short` or `already_done` when unpaid."""

    date: str
    target_seconds: int
    min_seconds: int
    spoken_seconds: int
    completed: bool
    xp: int
    sparks: int
    reason: Literal["too_short", "already_done"] | None


class Rewards(BaseModel):
    """Everything a session earned."""

    xp_gained: int
    xp_breakdown: list[XpLine]
    sparks_gained: int
    level_before: int
    level_after: int
    leveled_up: bool
    new_title: str | None
    personal_best: bool
    streak: RewardStreak
    new_badges: list[Badge]
    completed_quests: list[Quest]
    # Defaults keep results stored before these existed valid.
    comeback: ComebackReward | None = None
    challenge: ChallengeReward | None = None
