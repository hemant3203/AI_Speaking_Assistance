"""Streak rules, as pure functions over dates. The database layer only stores their results."""
from dataclasses import dataclass, field
from datetime import date, timedelta

FREEZE_LIMIT = 2
_MILESTONE_DAYS = 7
_WEEK_DAYS = 7


@dataclass(frozen=True)
class StreakUpdate:
    """The result of recording a qualifying session."""

    current: int
    longest: int
    freezes: int
    extended: bool
    freeze_used: int = 0
    freeze_earned: bool = False
    frozen_dates: list[date] = field(default_factory=list)


def apply_practice(
    today: date, last_practice: date | None, current: int, longest: int, freezes: int
) -> StreakUpdate:
    """Apply one qualifying session.

    `today` can fall before `last_practice` if the user moved west across timezones. That counts as
    the same day, because a clock change must not break or extend a streak.
    """
    if last_practice is not None and today <= last_practice:
        return StreakUpdate(current=current, longest=longest, freezes=freezes, extended=False)

    frozen_dates: list[date] = []
    if last_practice is None:
        new_current = 1
    else:
        missed = (today - last_practice).days - 1
        if missed == 0:
            new_current = current + 1
        elif missed <= freezes:
            frozen_dates = [last_practice + timedelta(days=offset) for offset in range(1, missed + 1)]
            freezes -= missed
            new_current = current + 1
        else:
            new_current = 1

    freeze_earned = new_current % _MILESTONE_DAYS == 0 and freezes < FREEZE_LIMIT
    if freeze_earned:
        freezes += 1
    return StreakUpdate(
        current=new_current,
        longest=max(longest, new_current),
        freezes=freezes,
        extended=True,
        freeze_used=len(frozen_dates),
        freeze_earned=freeze_earned,
        frozen_dates=frozen_dates,
    )


@dataclass(frozen=True)
class StreakStatus:
    """The streak as shown to the user right now."""

    current: int
    status: str
    practiced_today: bool


def read_status(today: date, last_practice: date | None, stored_current: int, freezes: int) -> StreakStatus:
    """Compute the visible streak at read time, so a broken streak shows 0 without any write."""
    if last_practice is None or stored_current == 0:
        return StreakStatus(0, "none", False)
    if today <= last_practice:
        return StreakStatus(stored_current, "active_today", True)
    if (today - last_practice).days - 1 <= freezes:
        return StreakStatus(stored_current, "at_risk", False)
    return StreakStatus(0, "none", False)


def next_milestone(current: int) -> int:
    """Return the next 7-day milestone strictly above the current streak."""
    return (current // _MILESTONE_DAYS + 1) * _MILESTONE_DAYS


def week_view(today: date, day_states: dict[date, str]) -> list[dict[str, str]]:
    """Return the last 7 days, oldest first. Today without practice is pending, not missed."""
    days = []
    for offset in range(_WEEK_DAYS - 1, -1, -1):
        day = today - timedelta(days=offset)
        state = day_states.get(day) or ("today_pending" if day == today else "missed")
        days.append({"date": day.isoformat(), "state": state})
    return days
