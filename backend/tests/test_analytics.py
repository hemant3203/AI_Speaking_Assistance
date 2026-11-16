"""Tests for the analytics overview."""
import re
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.services.gamification.rewards import finalise_session
from tests.conftest import API, create_session, make_outcome, register, run_sql

FILLER_TEXT = ("um " * 8 + " ".join(f"word{n}" for n in range(92))).strip()


def _add_session(client, days_ago: int = 0, mode: str = "impromptu", **outcome_kwargs) -> dict:
    session = create_session(client, mode=mode)
    day = date.fromisoformat(session["local_date"]) - timedelta(days=days_ago)
    run_sql("UPDATE practice_sessions SET local_date=:d WHERE id=:i", d=day, i=session["id"])
    finalise_session(session["id"], make_outcome(**outcome_kwargs))
    return session


def _overview(client, days: int = 30) -> dict:
    response = client.get(f"{API}/analytics/overview", params={"days": days})
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_data_returns_zeros_nulls_and_empty_arrays(client, user):
    for days in (7, 30, 90, 0):
        body = _overview(client, days)
        assert body["range_days"] == days
        assert body["summary"] == {
            "sessions": 0,
            "speaking_seconds": 0,
            "avg_score": None,
            "best_score": None,
            "avg_wpm": None,
            "avg_filler_per_100": None,
            "deltas": {"sessions": None, "avg_score": None, "avg_wpm": None, "avg_filler_per_100": None},
        }
        for key in ("score_trend", "skills", "focus_areas", "strengths", "pace_trend", "filler_trend",
                    "top_fillers", "modes", "heatmap"):
            assert body[key] == [], key
        assert body["pace_band"] == {"low": 120, "high": 160}


def test_invalid_range_is_422(client, user):
    assert client.get(f"{API}/analytics/overview", params={"days": 14}).status_code == 422


def test_summary_and_trends(client, user):
    _add_session(client, score=70, seconds=100)
    _add_session(client, score=90, seconds=120)
    body = _overview(client)
    summary = body["summary"]
    assert summary["sessions"] == 2 and summary["speaking_seconds"] == 220
    assert summary["avg_score"] == 80 and summary["best_score"] == 90
    assert len(body["score_trend"]) == 2 and body["score_trend"][0]["overall"] == 70
    assert set(body["score_trend"][0]) == {
        "session_id", "date", "overall", "pace", "fluency", "vocal_variety", "vocabulary", "confidence",
        "structure", "clarity", "engagement",
    }
    assert len(body["pace_trend"]) == 2 and len(body["filler_trend"]) == 2


def test_only_completed_sessions_count(client, user):
    create_session(client)
    session = create_session(client)
    finalise_session(session["id"], make_outcome(qualified=False))
    assert _overview(client)["summary"]["sessions"] == 0


def test_deltas_compare_with_the_previous_equal_period(client, user):
    _add_session(client, days_ago=10, score=60)
    _add_session(client, days_ago=1, score=80)
    _add_session(client, days_ago=2, score=80)
    deltas = _overview(client, 7)["summary"]["deltas"]
    assert deltas["sessions"] == 1 and deltas["avg_score"] == 20


def test_all_time_has_no_comparison(client, user):
    _add_session(client, days_ago=200, score=60)
    body = _overview(client, 0)
    assert body["summary"]["sessions"] == 1
    assert body["summary"]["deltas"]["avg_score"] is None
    assert body["heatmap"] == []


def test_range_filter_excludes_older_sessions(client, user):
    _add_session(client, days_ago=20)
    assert _overview(client, 7)["summary"]["sessions"] == 0
    assert _overview(client, 30)["summary"]["sessions"] == 1


def test_skills_have_previous_and_delta(client, user):
    _add_session(client, days_ago=10)
    _add_session(client, days_ago=1)
    skills = {skill["id"]: skill for skill in _overview(client, 7)["skills"]}
    assert len(skills) == 8
    assert skills["pace"]["samples"] == 1 and skills["pace"]["current"] == 90
    assert skills["pace"]["previous"] == 90 and skills["pace"]["delta"] == 0
    assert skills["pace"]["name"] == "Pace" and skills["pace"]["description"]


def test_focus_areas_are_the_three_weakest_and_cite_real_numbers(client, user):
    _add_session(client, transcript=FILLER_TEXT, score=90, seconds=60)
    body = _overview(client)
    focus = body["focus_areas"]
    assert len(focus) == 3
    scores = [area["score"] for area in focus]
    assert scores == sorted(scores)
    assert set(focus[0]) == {"skill", "name", "score", "delta", "why", "tip", "drill_mode"}
    assert all(re.search(r"\d", area["why"]) for area in focus)
    assert all(area["drill_mode"] in {"impromptu", "presentation", "interview", "storytelling", "persuasion"} for area in focus)

    weakest_ids = {area["skill"] for area in focus}
    assert not weakest_ids & {strength["skill"] for strength in body["strengths"]}


def test_fluency_advice_quotes_the_actual_filler_rate_and_word(client, user):
    _add_session(client, transcript=FILLER_TEXT, seconds=60)
    run_sql("UPDATE practice_sessions SET scores = scores || '{\"fluency\": 5}'")
    area = next(a for a in _overview(client)["focus_areas"] if a["skill"] == "fluency")
    assert "8.0 fillers per 100 words" in area["why"]
    assert '"um"' in area["why"] and '"um"' in area["tip"]


def test_pace_advice_quotes_the_actual_pace(client, user):
    _add_session(client, seconds=60, transcript=" ".join(f"w{n}" for n in range(200)))
    run_sql("UPDATE practice_sessions SET scores = scores || '{\"pace\": 1}'")
    area = next(a for a in _overview(client)["focus_areas"] if a["skill"] == "pace")
    assert "200 words per minute" in area["why"] and "40 above" in area["why"]
    assert "40 WPM" in area["tip"]


def test_degraded_sessions_are_left_out_of_filler_stats(client, user):
    _add_session(client, ai_scored=False, transcript=FILLER_TEXT, seconds=60)
    body = _overview(client)
    assert body["summary"]["sessions"] == 1
    assert body["summary"]["avg_filler_per_100"] is None
    assert body["filler_trend"] == [] and body["top_fillers"] == []
    skills = {skill["id"]: skill for skill in body["skills"]}
    assert skills["structure"]["current"] is None and skills["structure"]["samples"] == 0
    assert all(area["skill"] != "structure" for area in body["focus_areas"])
    assert all(area["skill"] != "fluency" or "fillers per 100" not in area["why"] for area in body["focus_areas"])


def test_top_fillers_and_modes(client, user):
    _add_session(client, transcript=FILLER_TEXT, seconds=60, mode="interview", score=60)
    _add_session(client, transcript=FILLER_TEXT, seconds=60, mode="interview", score=80)
    _add_session(client, mode="storytelling", score=50)
    body = _overview(client)
    assert body["top_fillers"] == [{"word": "um", "count": 16}]
    assert body["modes"][0] == {"mode": "interview", "name": "Interview", "sessions": 2, "avg_score": 70}
    assert body["modes"][1]["mode"] == "storytelling"


def test_heatmap_is_always_last_182_days_and_active_days_only(client, user):
    _add_session(client, days_ago=100, seconds=60)
    _add_session(client, days_ago=100, seconds=30)
    _add_session(client, days_ago=200)
    session = create_session(client)
    today = date.fromisoformat(session["local_date"])

    body = _overview(client, 7)
    assert body["summary"]["sessions"] == 0
    assert body["heatmap"] == [
        {"date": (today - timedelta(days=100)).isoformat(), "sessions": 2, "speaking_seconds": 90}
    ]


def test_analytics_are_isolated_between_users(client, user):
    _add_session(client)
    other = TestClient(app)
    register(other, email="b@example.com")
    assert _overview(other)["summary"]["sessions"] == 0
