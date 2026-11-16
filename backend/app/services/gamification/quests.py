"""Daily quests: deterministic selection, and progress computed from a day's activity."""
import hashlib
import random
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace
from typing import Any

BONUS_SPARKS = 10
_DAILY_QUEST_COUNT = 3
_ANCHOR_QUEST = "warm_up"


@dataclass(frozen=True)
class QuestDefinition:
    """One quest that can be offered."""

    id: str
    title: str
    description: str
    icon: str
    target: int
    xp: int
    sparks: int
    progress: Callable[[Any], float]


QUESTS = {
    quest.id: quest
    for quest in (
        QuestDefinition("warm_up", "Warm up", "Finish 1 session", "Flame", 1, 15, 5, lambda d: d.sessions),
        QuestDefinition("double_up", "Double up", "Finish 2 sessions", "Repeat", 2, 25, 5, lambda d: d.sessions),
        QuestDefinition(
            "three_minutes", "Three minutes", "Speak for 3 minutes in total", "Timer", 180, 25, 5,
            lambda d: d.speaking_seconds,
        ),
        QuestDefinition(
            "high_scorer", "High scorer", "Score at least 70 in a session", "Target", 1, 20, 5,
            lambda d: int(d.best_score >= 70),
        ),
        QuestDefinition(
            "clean_speech", "Clean speech", "Finish a session with at most 3 fillers per 100 words", "Sparkles",
            1, 25, 5, lambda d: int(d.low_filler_done),
        ),
        QuestDefinition(
            "in_the_zone", "In the zone", "Finish a session at 120-160 words per minute", "Gauge", 1, 20, 5,
            lambda d: int(d.on_pace_done),
        ),
        QuestDefinition(
            "mix_it_up", "Mix it up", "Practise 2 different modes", "Shuffle", 2, 25, 5, lambda d: len(d.modes),
        ),
    )
}

_EMPTY_DAY = SimpleNamespace(
    sessions=0, speaking_seconds=0.0, best_score=0, low_filler_done=False, on_pace_done=False, modes=[]
)


def quests_for_day(user_id: str, day: date) -> list[QuestDefinition]:
    """Choose a user's quests for a day, always including warm_up.

    This uses sha256 rather than `hash()`, which is randomised per process and would change a user's
    quests on every restart.
    """
    seed = hashlib.sha256(f"{user_id}:{day.isoformat()}".encode()).digest()
    pool = sorted(quest_id for quest_id in QUESTS if quest_id != _ANCHOR_QUEST)
    chosen = random.Random(seed).sample(pool, _DAILY_QUEST_COUNT - 1)
    return [QUESTS[_ANCHOR_QUEST], *(QUESTS[quest_id] for quest_id in chosen)]


def _item(quest: QuestDefinition, activity: Any, completed_ids: set[str]) -> dict[str, Any]:
    progress = min(quest.target, int(quest.progress(activity)))
    return {
        "id": quest.id,
        "title": quest.title,
        "description": quest.description,
        "icon": quest.icon,
        "progress": progress,
        "target": quest.target,
        "xp": quest.xp,
        "sparks": quest.sparks,
        "completed": quest.id in completed_ids or progress >= quest.target,
    }


def daily_quest_items(user_id: str, day: date, activity: Any | None, completed_ids: set[str]) -> list[dict[str, Any]]:
    """Return the day's quests with the user's progress."""
    return [_item(quest, activity or _EMPTY_DAY, completed_ids) for quest in quests_for_day(user_id, day)]
