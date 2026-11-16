"""Tests for the category score formulas."""
from app.services.analysis.audio_metrics import AudioMetrics
from app.services.analysis.scoring import (
    compute_local_scores,
    confidence_score,
    fluency_score,
    is_pace_in_band,
    overall_score,
    pace_score,
    vocabulary_score,
    vocal_variety_score,
)
from app.services.analysis.text_metrics import TextMetrics


def test_pace_full_marks_in_band_and_falls_off_both_sides():
    assert pace_score(120) == pace_score(140) == pace_score(160) == 100
    assert pace_score(100) == 70
    assert pace_score(180) == 70
    assert pace_score(20) == 0
    assert pace_score(400) == 0


def test_fluency_penalises_fillers_and_excess_pauses():
    assert fluency_score(0, 0.1) == 100
    assert fluency_score(2, 0.1) == 86
    assert fluency_score(0, 0.25) == 85
    assert fluency_score(50, 0.9) == 0


def test_fluency_ignores_unreliable_filler_counts():
    assert fluency_score(10, 0.1, fillers_reliable=False) == 100


def test_vocal_variety_peaks_in_the_middle():
    assert vocal_variety_score(0.0) == 20
    assert vocal_variety_score(0.6) == 100
    assert vocal_variety_score(0.2) < vocal_variety_score(0.4) < vocal_variety_score(0.6)
    assert vocal_variety_score(1.5) < 100


def test_vocabulary_is_length_adjusted():
    assert vocabulary_score(0, 0) == 0
    # Comparable richness at different lengths should score close together, not 2x apart.
    assert abs(vocabulary_score(35, 50) - vocabulary_score(150, 280)) <= 25
    assert vocabulary_score(150, 280) > vocabulary_score(60, 280)


def test_confidence_penalises_hedges_and_long_pauses():
    assert confidence_score(0, 0) == 100
    assert confidence_score(2, 1) == 78
    assert confidence_score(50, 50) == 0


def test_overall_weights_ai_categories_double():
    local_only = {"pace": 100, "fluency": 100, "vocal_variety": 100, "vocabulary": 100, "confidence": 100}
    assert overall_score({**local_only, "structure": None, "clarity": None, "engagement": None}) == 100
    # (5 * 100 + 6 * 50) / 11
    assert overall_score({**local_only, "structure": 50, "clarity": 50, "engagement": 50}) == 73


def test_overall_degraded_is_mean_of_local_categories():
    scores = {
        "pace": 90,
        "fluency": 70,
        "vocal_variety": 50,
        "vocabulary": 60,
        "confidence": 80,
        "structure": None,
        "clarity": None,
        "engagement": None,
    }
    assert overall_score(scores) == 70


def test_overall_with_nothing_is_none():
    assert overall_score({"pace": None}) is None


def test_local_scores_without_a_transcript_are_null_for_word_based_categories():
    scores = compute_local_scores(AudioMetrics(speaking_seconds=30, volume_variation=0.5), TextMetrics(), False)
    assert scores["pace"] is None and scores["vocabulary"] is None and scores["confidence"] is None
    assert scores["fluency"] is not None and scores["vocal_variety"] is not None


def test_pace_band_edges():
    assert is_pace_in_band(120) and is_pace_in_band(160)
    assert not is_pace_in_band(119.9) and not is_pace_in_band(None)
