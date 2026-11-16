"""Second takes: say the same speech again and earn a comeback bonus for beating the first one.

A take can be beaten on its overall score, on its grammar, or both, so fixing the grammar slips the
coach pointed out pays even when the rest of the speech scores about the same.
"""
from typing import Any

XP_PER_SCORE_POINT = 3
MAX_SCORE_XP = 45
XP_PER_GRAMMAR_POINT = 2
MAX_GRAMMAR_XP = 30
SCORE_SPARKS = 5
GRAMMAR_SPARKS = 5
# Daily cap, so deliberately weak takes can't be farmed for bonuses.
DAILY_LIMIT = 5


def grammar_score(feedback: dict[str, Any] | None) -> int | None:
    """Return a session's grammar score, or None when it wasn't measured."""
    grammar = (feedback or {}).get("grammar") or {}
    score = grammar.get("score")
    return score if isinstance(score, int) else None


def grammar_slip_count(feedback: dict[str, Any] | None) -> int | None:
    """Return how many grammar slips were flagged, or None when grammar wasn't measured."""
    if grammar_score(feedback) is None:
        return None
    return len(((feedback or {}).get("grammar") or {}).get("issues") or [])


def dedupe_key(parent_id: str) -> str:
    """The ledger key that lets each take be beaten for a bonus only once."""
    return f"comeback:{parent_id}"


def evaluate(
    parent_id: str,
    score_before: int,
    score_after: int,
    feedback_before: dict[str, Any] | None,
    feedback_after: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare a second take with the first. The bonus is what it would earn, before any limits."""
    grammar_before = grammar_score(feedback_before)
    grammar_after = grammar_score(feedback_after)
    score_gain = max(0, score_after - score_before)
    grammar_gain = (
        max(0, grammar_after - grammar_before) if grammar_before is not None and grammar_after is not None else 0
    )
    xp = min(MAX_SCORE_XP, score_gain * XP_PER_SCORE_POINT) + min(MAX_GRAMMAR_XP, grammar_gain * XP_PER_GRAMMAR_POINT)
    sparks = (SCORE_SPARKS if score_gain else 0) + (GRAMMAR_SPARKS if grammar_gain else 0)
    return {
        "parent_id": parent_id,
        "score_before": score_before,
        "score_after": score_after,
        "grammar_before": grammar_before,
        "grammar_after": grammar_after,
        "slips_before": grammar_slip_count(feedback_before),
        "slips_after": grammar_slip_count(feedback_after),
        "improved": xp > 0,
        "xp": xp,
        "sparks": sparks,
        "reason": None if xp > 0 else "not_improved",
    }
