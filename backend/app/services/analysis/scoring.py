"""Category score formulas. All are pure functions returning integers from 0 to 100."""
from app.services.analysis.audio_metrics import AudioMetrics
from app.services.analysis.text_metrics import TextMetrics

PACE_LOW = 120
PACE_HIGH = 160
LOW_FILLER_PER_100 = 3.0
CLEAN_FILLER_PER_100 = 1.0

LOCAL_CATEGORIES = ("pace", "fluency", "vocal_variety", "vocabulary", "confidence")
AI_CATEGORIES = ("structure", "clarity", "engagement")
ALL_CATEGORIES = (*LOCAL_CATEGORIES, *AI_CATEGORIES)
_CATEGORY_WEIGHTS = {**dict.fromkeys(LOCAL_CATEGORIES, 1.0), **dict.fromkeys(AI_CATEGORIES, 2.0)}

_PACE_PENALTY_PER_WPM = 1.5
_FILLER_PENALTY = 7.0
_PAUSE_RATIO_ALLOWANCE = 0.15
_PAUSE_RATIO_PENALTY = 150.0
_VARIETY_LOW = 0.45
_VARIETY_HIGH = 0.90
_HEDGE_PENALTY = 8.0
_LONG_PAUSE_PENALTY_PER_MINUTE = 6.0
# Unique words grow more slowly than total words. Dividing by N^0.75 keeps a short and a long speech
# comparable, where a plain unique/total ratio would always favour the short one.
_VOCABULARY_EXPONENT = 0.75
_VOCABULARY_LOW = 1.0
_VOCABULARY_HIGH = 2.7


def _clamp(value: float) -> int:
    return int(round(min(100.0, max(0.0, value))))


def pace_score(wpm: float) -> int:
    """Score WPM: full marks inside the 120-160 band, falling off on both sides."""
    distance = max(PACE_LOW - wpm, wpm - PACE_HIGH, 0)
    return _clamp(100 - distance * _PACE_PENALTY_PER_WPM)


def fluency_score(filler_per_100: float, pause_ratio: float, fillers_reliable: bool = True) -> int:
    """Score fluency from fillers and pauses.

    Live transcription strips fillers, so unreliable counts are ignored. Otherwise a degraded session
    would get a free "no fillers" bonus.
    """
    filler_penalty = filler_per_100 * _FILLER_PENALTY if fillers_reliable else 0.0
    pause_penalty = max(0.0, pause_ratio - _PAUSE_RATIO_ALLOWANCE) * _PAUSE_RATIO_PENALTY
    return _clamp(100 - filler_penalty - pause_penalty)


def vocal_variety_score(volume_variation: float) -> int:
    """Score volume variation: flat delivery scores low, and so does erratic delivery."""
    if volume_variation < _VARIETY_LOW:
        return _clamp(20 + volume_variation / _VARIETY_LOW * 80)
    if volume_variation <= _VARIETY_HIGH:
        return 100
    return _clamp(100 - (volume_variation - _VARIETY_HIGH) * 66)


def vocabulary_score(unique_words: int, content_words: int) -> int:
    """Score the length-adjusted unique-word ratio."""
    if content_words == 0:
        return 0
    adjusted = unique_words / content_words**_VOCABULARY_EXPONENT
    return _clamp((adjusted - _VOCABULARY_LOW) / (_VOCABULARY_HIGH - _VOCABULARY_LOW) * 100)


def confidence_score(hedges_per_100: float, long_pauses_per_minute: float) -> int:
    """Score confidence from hedging language and long pauses."""
    return _clamp(100 - hedges_per_100 * _HEDGE_PENALTY - long_pauses_per_minute * _LONG_PAUSE_PENALTY_PER_MINUTE)


def compute_local_scores(audio: AudioMetrics, text: TextMetrics, fillers_reliable: bool) -> dict[str, int | None]:
    """Compute the five local categories.

    Categories that need words are null when there is no transcript at all. That only happens on the
    degraded path, and a made-up number would be worse than none.
    """
    minutes = audio.speaking_seconds / 60
    long_pauses_per_minute = audio.long_pause_count / minutes if minutes else 0.0
    has_words = text.word_count > 0
    return {
        "pace": pace_score(text.wpm) if has_words and text.wpm is not None else None,
        "fluency": fluency_score(text.filler_per_100, audio.pause_ratio, fillers_reliable and has_words),
        "vocal_variety": vocal_variety_score(audio.volume_variation),
        "vocabulary": vocabulary_score(text.unique_words, text.content_words) if has_words else None,
        "confidence": confidence_score(text.hedges_per_100, long_pauses_per_minute) if has_words else None,
    }


def overall_score(scores: dict[str, int | None]) -> int | None:
    """Return the weighted mean of available categories, with AI categories counting double."""
    available = [(score, _CATEGORY_WEIGHTS[name]) for name, score in scores.items() if score is not None]
    if not available:
        return None
    total_weight = sum(weight for _, weight in available)
    return _clamp(sum(score * weight for score, weight in available) / total_weight)


def is_pace_in_band(wpm: float | None) -> bool:
    """Report whether a pace falls inside the target band."""
    return wpm is not None and PACE_LOW <= wpm <= PACE_HIGH
