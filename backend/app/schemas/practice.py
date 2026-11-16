"""Request and response models for practice sessions."""
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, model_validator, StringConstraints

from app.models.practice import PracticeSession
from app.schemas.common import UtcDatetime, strip_control_characters
from app.schemas.gamification import ChallengeReward, ComebackReward, Rewards
from app.services.analysis.scoring import ALL_CATEGORIES
from app.services.catalog import FREE_TALK_TOPIC
from app.services.gamification.challenges import LENGTHS as CHALLENGE_LENGTHS

ModeId = Literal["impromptu", "presentation", "interview", "storytelling", "persuasion"]
LanguageId = Literal["en", "hi"]
Topic = Annotated[
    str,
    AfterValidator(strip_control_characters),
    StringConstraints(strip_whitespace=True, min_length=3, max_length=200),
]


class CreateSessionRequest(BaseModel):
    """Body of POST /practice/sessions.

    `retry_of` makes a second take of an earlier session, and `challenge` takes on today's challenge.
    Either way the server sets the topic and mode itself, so `topic` isn't needed.
    """

    mode: ModeId
    topic: Topic | None = None
    free_talk: bool = False
    target_seconds: Literal[60, 120, 180, 300, 600, 900]
    language: LanguageId
    retry_of: uuid.UUID | None = None
    challenge: bool = False

    @model_validator(mode="after")
    def _needs_a_topic_or_free_talk(self) -> "CreateSessionRequest":
        if self.challenge and self.retry_of is None and self.target_seconds not in CHALLENGE_LENGTHS:
            raise ValueError("The daily challenge is 3 or 5 minutes long.")
        if self.retry_of is not None or self.challenge:
            return self
        if self.free_talk:
            self.topic = FREE_TALK_TOPIC
        elif self.topic is None:
            raise ValueError("Choose a topic or free talk.")
        return self


class ModeOut(BaseModel):
    """One practice mode with its suggested topics."""

    id: str
    name: str
    description: str
    icon: str
    topics: list[str]
    topics_hi: list[str]


class LanguageOut(BaseModel):
    """One supported language."""

    id: str
    name: str


class CatalogOut(BaseModel):
    """Body of GET /practice/catalog."""

    modes: list[ModeOut]
    durations: list[int]
    languages: list[LanguageOut]


class Scores(BaseModel):
    """Category scores. Null means not measured: unscored, too short, or AI categories when degraded."""

    pace: int | None = None
    fluency: int | None = None
    vocal_variety: int | None = None
    vocabulary: int | None = None
    confidence: int | None = None
    structure: int | None = None
    clarity: int | None = None
    engagement: int | None = None


class GrammarIssueOut(BaseModel):
    """One grammar slip: the words as said, the corrected words, and the rule."""

    said: str
    better: str
    why: str
    type: str


class Grammar(BaseModel):
    """How grammatical the speech was, and the slips worth fixing."""

    score: int
    issues: list[GrammarIssueOut]


class Feedback(BaseModel):
    """The analysis model's written feedback. `grammar` is null for sessions scored before it existed."""

    summary: str
    strengths: list[str]
    improvements: list[str]
    next_drill: str
    grammar: Grammar | None = None


class SessionSummary(BaseModel):
    """A session as shown in lists."""

    id: str
    mode: str
    topic: str
    free_talk: bool
    language: str
    status: str
    started_at: UtcDatetime
    local_date: date
    speaking_seconds: float | None
    overall_score: int | None
    wpm: float | None
    filler_per_100: float | None
    xp_awarded: int
    sparks_awarded: int
    retry_of: str | None
    challenge_date: date | None

    @classmethod
    def from_row(cls, row: PracticeSession) -> "SessionSummary":
        """Build from a database row."""
        return cls(**_summary_fields(row))


class SessionDetail(SessionSummary):
    """A session with all of its metrics, feedback and transcripts."""

    target_seconds: int
    coach_id: str
    ended_at: UtcDatetime | None
    word_count: int | None
    filler_count: int | None
    filler_breakdown: dict[str, int]
    hedge_count: int | None
    pause_count: int | None
    longest_pause_seconds: float | None
    pause_ratio: float | None
    volume_variation: float | None
    vocabulary_ratio: float | None
    scores: Scores
    ai_scored: bool
    analysis_model: str | None
    filler_counts_reliable: bool
    feedback: Feedback | None
    transcript: str | None
    coach_transcript: str | None
    # How this take did as a second take and as a daily challenge. Null when it was neither, or isn't scored.
    comeback: ComebackReward | None
    challenge: ChallengeReward | None

    @classmethod
    def from_row(cls, row: PracticeSession) -> "SessionDetail":
        """Build from a database row. The session must still be attached, to load deferred text."""
        # Only a finalised session has a result, and skipping the rest avoids loading a deferred column.
        rewards = ((row.result_payload or {}).get("rewards") or {}) if row.finalised_at is not None else {}
        return cls(
            **_summary_fields(row),
            target_seconds=row.target_seconds,
            coach_id=row.coach_id,
            ended_at=row.ended_at,
            word_count=row.word_count,
            filler_count=row.filler_count,
            filler_breakdown=row.filler_breakdown or {},
            hedge_count=row.hedge_count,
            pause_count=row.pause_count,
            longest_pause_seconds=row.longest_pause_seconds,
            pause_ratio=row.pause_ratio,
            volume_variation=row.volume_variation,
            vocabulary_ratio=row.vocabulary_ratio,
            scores=Scores(**{name: (row.scores or {}).get(name) for name in ALL_CATEGORIES}),
            ai_scored=row.ai_scored,
            analysis_model=row.analysis_model,
            filler_counts_reliable=row.filler_counts_reliable,
            feedback=row.feedback,
            transcript=row.transcript,
            coach_transcript=row.coach_transcript,
            comeback=rewards.get("comeback"),
            challenge=rewards.get("challenge"),
        )


def _summary_fields(row: PracticeSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "mode": row.mode,
        "topic": row.topic,
        "free_talk": row.free_talk,
        "language": row.language,
        "status": row.status,
        "started_at": row.started_at,
        "local_date": row.local_date,
        "speaking_seconds": row.speaking_seconds,
        "overall_score": row.overall_score,
        "wpm": row.wpm,
        "filler_per_100": row.filler_per_100,
        "xp_awarded": row.xp_awarded,
        "sparks_awarded": row.sparks_awarded,
        "retry_of": row.retry_of,
        "challenge_date": row.challenge_date,
    }


class SessionList(BaseModel):
    """Body of GET /practice/sessions."""

    items: list[SessionSummary]
    total: int


class SessionResult(BaseModel):
    """The payload of the `session_result` WebSocket frame."""

    session: SessionDetail
    qualified: bool
    disqualified_reason: str | None
    rewards: Rewards
