"""Level math, and the XP and sparks formulas for one session."""
from dataclasses import dataclass

_LEVEL_TITLES = {
    1: "Nervous Newcomer",
    2: "Mic Checker",
    3: "Warm-Up Act",
    4: "Steady Voice",
    5: "Confident Speaker",
    6: "Room Reader",
    7: "Crowd Pleaser",
    8: "Stage Regular",
    9: "Keynote Speaker",
}
_LEGEND_TITLE = "Spotlight Legend"

_BASE_XP = 20
_MAX_TIME_XP = 50
_XP_PER_MINUTE = 10
_PERSONAL_BEST_XP = 15
_STREAK_BONUS_PER_DAY = 0.05
_STREAK_BONUS_MAX_DAYS = 10

_BASE_SPARKS = 5
_FIRST_OF_DAY_SPARKS = 5
_HIGH_SCORE_SPARKS = 5
_HIGH_SCORE = 80


def xp_to_reach(level: int) -> int:
    """Return the cumulative XP needed to reach a level."""
    return 50 * level * (level - 1)


def level_for_xp(xp: int) -> int:
    """Return the level a cumulative XP total corresponds to."""
    level = 1
    while xp >= xp_to_reach(level + 1):
        level += 1
    return level


def level_title(level: int) -> str:
    """Return the display title of a level."""
    return _LEVEL_TITLES.get(level, _LEGEND_TITLE)


@dataclass(frozen=True)
class LevelProgress:
    """Where a user stands within their current level."""

    level: int
    title: str
    xp_into_level: int
    xp_for_next_level: int


def level_progress(xp: int) -> LevelProgress:
    """Describe progress through the current level."""
    level = level_for_xp(xp)
    floor = xp_to_reach(level)
    return LevelProgress(level, level_title(level), xp - floor, xp_to_reach(level + 1) - floor)


def session_xp(
    speaking_seconds: float, overall_score: int, personal_best: bool, streak: int
) -> tuple[int, list[dict[str, int | str]]]:
    """Return a session's XP and a breakdown that adds up to exactly that total."""
    time_xp = min(_MAX_TIME_XP, _XP_PER_MINUTE * speaking_seconds / 60)
    score_xp = overall_score * 0.5
    best_xp = _PERSONAL_BEST_XP if personal_best else 0
    subtotal = _BASE_XP + time_xp + score_xp + best_xp
    total = round(subtotal * (1 + _STREAK_BONUS_PER_DAY * min(streak, _STREAK_BONUS_MAX_DAYS)))

    # The score line absorbs rounding, so the lines always add up and the streak line is purely streak.
    rounded_subtotal = round(subtotal)
    breakdown: list[dict[str, int | str]] = [
        {"label": "Session complete", "xp": _BASE_XP},
        {"label": "Speaking time", "xp": round(time_xp)},
        {"label": "Score", "xp": rounded_subtotal - _BASE_XP - round(time_xp) - best_xp},
    ]
    if personal_best:
        breakdown.append({"label": "Personal best", "xp": best_xp})
    streak_xp = total - rounded_subtotal
    if streak_xp:
        breakdown.append({"label": "Streak bonus", "xp": streak_xp})
    return total, breakdown


def session_sparks(first_of_day: bool, overall_score: int) -> int:
    """Return the sparks a session earns."""
    sparks = _BASE_SPARKS
    if first_of_day:
        sparks += _FIRST_OF_DAY_SPARKS
    if overall_score >= _HIGH_SCORE:
        sparks += _HIGH_SCORE_SPARKS
    return sparks
