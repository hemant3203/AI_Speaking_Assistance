"""Response models for analytics."""
from pydantic import BaseModel


class Deltas(BaseModel):
    """Change against the previous equal period. Null when that period has no data."""

    sessions: int | None
    avg_score: int | None
    avg_wpm: int | None
    avg_filler_per_100: float | None


class Summary(BaseModel):
    """Headline numbers for the range."""

    sessions: int
    speaking_seconds: int
    avg_score: int | None
    best_score: int | None
    avg_wpm: int | None
    avg_filler_per_100: float | None
    deltas: Deltas


class ScorePoint(BaseModel):
    """One session's scores in the trend."""

    session_id: str
    date: str
    overall: int | None
    pace: int | None
    fluency: int | None
    vocal_variety: int | None
    vocabulary: int | None
    confidence: int | None
    structure: int | None
    clarity: int | None
    engagement: int | None


class SkillOut(BaseModel):
    """One skill's average in this range and the previous one."""

    id: str
    name: str
    description: str
    current: int | None
    previous: int | None
    delta: int | None
    samples: int


class FocusArea(BaseModel):
    """A weak skill, with advice based on the user's own numbers."""

    skill: str
    name: str
    score: int
    delta: int | None
    why: str
    tip: str
    drill_mode: str


class Strength(BaseModel):
    """A strong skill."""

    skill: str
    name: str
    score: int


class PacePoint(BaseModel):
    """One session's pace."""

    session_id: str
    date: str
    wpm: float


class PaceBand(BaseModel):
    """The target pace band."""

    low: int
    high: int


class FillerPoint(BaseModel):
    """One session's filler rate."""

    session_id: str
    date: str
    per_100: float


class TopFiller(BaseModel):
    """A filler word and how often it was used."""

    word: str
    count: int


class ModeStat(BaseModel):
    """Totals for one practice mode."""

    mode: str
    name: str
    sessions: int
    avg_score: int | None


class HeatmapDay(BaseModel):
    """One active day in the heatmap."""

    date: str
    sessions: int
    speaking_seconds: int


class Overview(BaseModel):
    """Body of GET /analytics/overview."""

    range_days: int
    summary: Summary
    score_trend: list[ScorePoint]
    skills: list[SkillOut]
    focus_areas: list[FocusArea]
    strengths: list[Strength]
    pace_trend: list[PacePoint]
    pace_band: PaceBand
    filler_trend: list[FillerPoint]
    top_fillers: list[TopFiller]
    modes: list[ModeStat]
    heatmap: list[HeatmapDay]
