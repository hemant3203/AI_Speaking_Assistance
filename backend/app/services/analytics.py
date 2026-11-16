"""Builds the analytics overview from a user's completed sessions."""
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from statistics import fmean
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.practice import PracticeSession
from app.services.analysis.scoring import ALL_CATEGORIES, PACE_HIGH, PACE_LOW
from app.services.catalog import MODE_NAMES

_HEATMAP_DAYS = 182
_TOP_FILLER_COUNT = 5
_FOCUS_AREA_COUNT = 3
_STRENGTH_COUNT = 3
_MIN_STRENGTH_SCORE = 60

_SKILLS = {
    "pace": ("Pace", "How close your speaking speed is to the 120-160 WPM band.", "presentation"),
    "fluency": ("Fluency", "How free your speech is from fillers and stalled pauses.", "impromptu"),
    "vocal_variety": ("Vocal Variety", "How much your volume moves to keep listeners engaged.", "storytelling"),
    "vocabulary": ("Vocabulary", "How varied your word choice is for the length of your speech.", "persuasion"),
    "confidence": ("Confidence", "How free you are of hedging language and long hesitations.", "interview"),
    "structure": ("Structure", "How clear your opening, progression and ending are.", "presentation"),
    "clarity": ("Clarity", "How easy your ideas are to follow.", "interview"),
    "engagement": ("Engagement", "How well you hold an audience's interest.", "storytelling"),
}


def _mean(values: Iterable[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return fmean(present) if present else None


def _rounded(value: float | None) -> int | None:
    return None if value is None else round(value)


def _difference(current: float | None, previous: float | None, digits: int | None = 0) -> Any:
    if current is None or previous is None:
        return None
    return round(current - previous, digits) if digits else round(current - previous)


def _score(row: PracticeSession, category: str) -> int | None:
    return (row.scores or {}).get(category)


def _reliable(rows: Iterable[PracticeSession]) -> list[PracticeSession]:
    # Live transcription strips fillers, so degraded sessions would make the user look falsely clean.
    return [row for row in rows if row.filler_counts_reliable]


def _summary(rows: list[PracticeSession], previous: list[PracticeSession]) -> dict[str, Any]:
    avg_score = _mean(row.overall_score for row in rows)
    avg_wpm = _mean(row.wpm for row in rows)
    avg_filler = _mean(row.filler_per_100 for row in _reliable(rows))
    prev_score = _mean(row.overall_score for row in previous)
    prev_wpm = _mean(row.wpm for row in previous)
    prev_filler = _mean(row.filler_per_100 for row in _reliable(previous))
    return {
        "sessions": len(rows),
        "speaking_seconds": round(sum(row.speaking_seconds or 0 for row in rows)),
        "avg_score": _rounded(avg_score),
        "best_score": max((row.overall_score for row in rows if row.overall_score is not None), default=None),
        "avg_wpm": _rounded(avg_wpm),
        "avg_filler_per_100": None if avg_filler is None else round(avg_filler, 1),
        "deltas": {
            "sessions": len(rows) - len(previous) if previous else None,
            "avg_score": _difference(avg_score, prev_score),
            "avg_wpm": _difference(avg_wpm, prev_wpm),
            "avg_filler_per_100": _difference(avg_filler, prev_filler, digits=1),
        },
    }


def _skills(rows: list[PracticeSession], previous: list[PracticeSession]) -> list[dict[str, Any]]:
    if not rows:
        return []
    skills = []
    for category in ALL_CATEGORIES:
        name, description, _ = _SKILLS[category]
        values = [score for row in rows if (score := _score(row, category)) is not None]
        current = _mean(values)
        earlier = _mean(_score(row, category) for row in previous)
        skills.append(
            {
                "id": category,
                "name": name,
                "description": description,
                "current": _rounded(current),
                "previous": _rounded(earlier),
                "delta": _difference(current, earlier),
                "samples": len(values),
            }
        )
    return skills


def _top_fillers(rows: Iterable[PracticeSession]) -> list[dict[str, Any]]:
    totals: Counter[str] = Counter()
    for row in _reliable(rows):
        totals.update(row.filler_breakdown or {})
    return [{"word": word, "count": count} for word, count in totals.most_common(_TOP_FILLER_COUNT)]


def _focus_copy(skill: dict[str, Any], rows: list[PracticeSession]) -> tuple[str, str]:
    """Write the advice for a weak skill, citing the numbers it is based on."""
    category, score, samples = skill["id"], skill["current"], skill["samples"]
    runs = f"{samples} session{'s' if samples != 1 else ''}"

    if category == "pace":
        wpm = _mean(row.wpm for row in rows) or 0
        if wpm < PACE_LOW:
            return (
                f"You average {wpm:.0f} words per minute, {PACE_LOW - wpm:.0f} below the {PACE_LOW}-{PACE_HIGH} band.",
                f"Lift your pace by about {PACE_LOW - wpm:.0f} WPM. Plan fewer pauses mid-sentence and rehearse your opening at a brisker speed.",
            )
        if wpm > PACE_HIGH:
            return (
                f"You average {wpm:.0f} words per minute, {wpm - PACE_HIGH:.0f} above the {PACE_LOW}-{PACE_HIGH} band.",
                f"Slow down by about {wpm - PACE_HIGH:.0f} WPM. Take a full breath at the end of each key sentence.",
            )
        return (
            f"You average {wpm:.0f} words per minute, but individual sessions drift out of the {PACE_LOW}-{PACE_HIGH} band.",
            "Aim for a steady pace from start to finish by rehearsing with a timer and checking the halfway point.",
        )

    if category == "fluency":
        fillers = _mean(row.filler_per_100 for row in _reliable(rows))
        pause_ratio = _mean(row.pause_ratio for row in rows) or 0
        top = _top_fillers(rows)
        if fillers is None:
            return (
                f"Pauses take up {pause_ratio:.0%} of your speaking time.",
                "Practise moving between ideas without stopping: state your next point in the first words after a pause.",
            )
        top_word = f', most often "{top[0]["word"]}"' if top else ""
        replace = f'Replace "{top[0]["word"]}"' if top else "Replace each filler"
        return (
            f"You average {fillers:.1f} fillers per 100 words{top_word}, and pauses take up {pause_ratio:.0%} of your speaking time.",
            f"{replace} with a silent one-second pause. Your next goal is under {max(1, fillers - 2):.0f} per 100 words.",
        )

    if category == "vocal_variety":
        variation = _mean(row.volume_variation for row in rows) or 0
        return (
            f"Your volume variation averages {variation:.2f}, where lively delivery usually sits between 0.45 and 0.90.",
            "Choose one key word per sentence and say it noticeably louder or softer than the rest.",
        )

    if category == "vocabulary":
        ratio = _mean(row.vocabulary_ratio for row in rows) or 0
        return (
            f"{ratio:.0%} of your words are unique, so you are repeating yourself more than you need to.",
            "Before your next speech, write down three alternatives for the word you expect to use most.",
        )

    if category == "confidence":
        hedges = _mean(
            100 * (row.hedge_count or 0) / row.word_count for row in rows if row.word_count
        ) or 0
        longest = _mean(row.longest_pause_seconds for row in rows) or 0
        return (
            f"You use {hedges:.1f} hedges per 100 words, and your longest pause averages {longest:.1f} seconds.",
            'Turn "I think" and "maybe" into direct statements. If you lose your place, pause for under a second and restate your last point.',
        )

    advice = {
        "structure": "Open by stating your point in one sentence, give two supporting ideas, then end by repeating it.",
        "clarity": "Replace one abstract claim with a concrete example or number in your next speech.",
        "engagement": "Start with a question or a short story, and tie your examples to what the audience cares about.",
    }[category]
    return f"Your {skill['name'].lower()} averages {score} out of 100 across {runs}.", advice


def _focus_and_strengths(
    skills: list[dict[str, Any]], rows: list[PracticeSession]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scored = sorted((skill for skill in skills if skill["current"] is not None), key=lambda skill: skill["current"])
    weakest = scored[:_FOCUS_AREA_COUNT]
    focus_areas = []
    for skill in weakest:
        why, tip = _focus_copy(skill, rows)
        focus_areas.append(
            {
                "skill": skill["id"],
                "name": skill["name"],
                "score": skill["current"],
                "delta": skill["delta"],
                "why": why,
                "tip": tip,
                "drill_mode": _SKILLS[skill["id"]][2],
            }
        )
    strongest = [
        skill for skill in reversed(scored[_FOCUS_AREA_COUNT:]) if skill["current"] >= _MIN_STRENGTH_SCORE
    ][:_STRENGTH_COUNT]
    return focus_areas, [{"skill": s["id"], "name": s["name"], "score": s["current"]} for s in strongest]


def _modes(rows: list[PracticeSession]) -> list[dict[str, Any]]:
    by_mode: dict[str, list[PracticeSession]] = defaultdict(list)
    for row in rows:
        by_mode[row.mode].append(row)
    return [
        {
            "mode": mode,
            "name": MODE_NAMES.get(mode, mode),
            "sessions": len(mode_rows),
            "avg_score": _rounded(_mean(row.overall_score for row in mode_rows)),
        }
        for mode, mode_rows in sorted(by_mode.items(), key=lambda item: -len(item[1]))
    ]


def _heatmap(rows: list[PracticeSession], today: date) -> list[dict[str, Any]]:
    start = today - timedelta(days=_HEATMAP_DAYS - 1)
    days: dict[date, list[float]] = defaultdict(lambda: [0, 0.0])
    for row in rows:
        if row.local_date >= start:
            days[row.local_date][0] += 1
            days[row.local_date][1] += row.speaking_seconds or 0
    return [
        {"date": day.isoformat(), "sessions": int(totals[0]), "speaking_seconds": round(totals[1])}
        for day, totals in sorted(days.items())
    ]


def build_overview(db: Session, user_id: str, days: int, today: date) -> dict[str, Any]:
    """Return the body of GET /analytics/overview. `days` of 0 means all time, with nothing to compare."""
    all_rows = list(
        db.scalars(
            select(PracticeSession)
            .where(PracticeSession.user_id == user_id, PracticeSession.status == "completed")
            .order_by(PracticeSession.started_at)
        )
    )
    if days:
        start = today - timedelta(days=days - 1)
        previous_start = start - timedelta(days=days)
        rows = [row for row in all_rows if row.local_date >= start]
        previous = [row for row in all_rows if previous_start <= row.local_date < start]
    else:
        rows, previous = all_rows, []

    skills = _skills(rows, previous)
    focus_areas, strengths = _focus_and_strengths(skills, rows)

    return {
        "range_days": days,
        "summary": _summary(rows, previous),
        "score_trend": [
            {
                "session_id": row.id,
                "date": row.local_date.isoformat(),
                "overall": row.overall_score,
                **{category: _score(row, category) for category in ALL_CATEGORIES},
            }
            for row in rows
        ],
        "skills": skills,
        "focus_areas": focus_areas,
        "strengths": strengths,
        "pace_trend": [
            {"session_id": row.id, "date": row.local_date.isoformat(), "wpm": row.wpm}
            for row in rows
            if row.wpm is not None
        ],
        "pace_band": {"low": PACE_LOW, "high": PACE_HIGH},
        "filler_trend": [
            {"session_id": row.id, "date": row.local_date.isoformat(), "per_100": row.filler_per_100}
            for row in _reliable(rows)
            if row.filler_per_100 is not None
        ],
        "top_fillers": _top_fillers(rows),
        "modes": _modes(rows),
        "heatmap": _heatmap(all_rows, today),
    }
