"""Tests for the catalog, session endpoints, user data isolation and health."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.logging import SafeFormatter, configure_logging, redact
from app.main import app
from app.services.gamification.rewards import finalise_session
from app.services.live.mock import MockProvider
from tests.conftest import API, create_session, make_outcome, register, run_sql


def test_requires_auth(client):
    for path in ("/practice/catalog", "/practice/sessions", "/gamification/profile", "/analytics/overview"):
        response = client.get(f"{API}{path}")
        assert response.status_code == 401 and response.json()["code"] == "not_authenticated"


def test_catalog_shape_and_content(client, user):
    body = client.get(f"{API}/practice/catalog").json()
    assert {mode["id"] for mode in body["modes"]} == {
        "impromptu", "presentation", "interview", "storytelling", "persuasion",
    }
    for mode in body["modes"]:
        assert len(mode["topics"]) >= 6 and mode["icon"] and mode["description"] and mode["name"]
    assert body["durations"] == [60, 120, 180, 300, 600, 900]
    assert body["languages"] == [{"id": "en", "name": "English"}, {"id": "hi", "name": "Hindi"}]


def test_every_mode_has_hindi_topics_written_in_hindi(client, user):
    for mode in client.get(f"{API}/practice/catalog").json()["modes"]:
        assert len(mode["topics_hi"]) >= 6
        for topic in mode["topics_hi"]:
            assert 3 <= len(topic) <= 200 and any("\u0900" <= ch <= "\u097f" for ch in topic)


def test_hindi_session_can_use_a_hindi_topic(client, user):
    topic = "अपने बारे में बताइए"
    response = client.post(
        f"{API}/practice/sessions",
        json={"mode": "interview", "topic": topic, "target_seconds": 60, "language": "hi"},
    )
    assert response.status_code == 201
    assert response.json()["language"] == "hi" and response.json()["topic"] == topic


def test_create_session_returns_a_full_detail(client, user):
    body = create_session(client)
    assert body["status"] == "created" and body["coach_id"] == "mentor" and body["target_seconds"] == 60
    assert body["analysis_model"] is None and body["ai_scored"] is False and body["feedback"] is None
    assert set(body["scores"]) == {
        "pace", "fluency", "vocal_variety", "vocabulary", "confidence", "structure", "clarity", "engagement",
    }
    assert body["filler_breakdown"] == {} and body["xp_awarded"] == 0


@pytest.mark.parametrize(
    "change",
    [{"mode": "karaoke"}, {"topic": "hi"}, {"topic": "x" * 201}, {"target_seconds": 45}, {"language": "fr"}, {"language": "hinglish"}],
)
def test_create_session_validation(client, user, change):
    body = {"mode": "impromptu", "topic": "A good topic", "target_seconds": 60, "language": "en", **change}
    assert client.post(f"{API}/practice/sessions", json=body).status_code == 422


def test_create_session_daily_limit(client, user):
    today = client.get(f"{API}/gamification/profile").json()["daily_quests"]["date"]
    run_sql(
        "INSERT INTO daily_activity (user_id, local_date, sessions, speaking_seconds, live_seconds, best_score,"
        " low_filler_done, on_pace_done, modes) VALUES (:u, :d, 0, 0, 1800, 0, false, false, '[]')",
        u=user["id"], d=today,
    )
    response = client.post(
        f"{API}/practice/sessions", json={"mode": "impromptu", "topic": "topic", "target_seconds": 60, "language": "en"}
    )
    assert response.status_code == 429 and response.json()["code"] == "daily_limit_reached"
    assert client.get(f"{API}/gamification/profile").json()["limits"]["remaining_seconds"] == 0


def test_create_session_coach_unavailable(client, user):
    class Unavailable(MockProvider):
        def is_available(self):
            return False

    app.state.live_provider = Unavailable()
    response = client.post(
        f"{API}/practice/sessions", json={"mode": "impromptu", "topic": "topic", "target_seconds": 60, "language": "en"}
    )
    assert response.status_code == 503 and response.json()["code"] == "coach_unavailable"


def test_list_hides_created_and_abandoned_and_is_newest_first(client, user):
    create_session(client)
    abandoned = create_session(client)
    run_sql("UPDATE practice_sessions SET status='abandoned' WHERE id=:i", i=abandoned["id"])
    first = create_session(client, mode="interview")
    second = create_session(client, mode="storytelling")
    finalise_session(first["id"], make_outcome())
    finalise_session(second["id"], make_outcome())
    run_sql("UPDATE practice_sessions SET started_at = started_at - interval '1 hour' WHERE id=:i", i=first["id"])

    body = client.get(f"{API}/practice/sessions").json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [second["id"], first["id"]]
    assert "transcript" not in body["items"][0]

    filtered = client.get(f"{API}/practice/sessions", params={"mode": "interview"}).json()
    assert [item["id"] for item in filtered["items"]] == [first["id"]]

    page = client.get(f"{API}/practice/sessions", params={"limit": 1, "offset": 1}).json()
    assert page["total"] == 2 and [item["id"] for item in page["items"]] == [first["id"]]


def test_analysis_model_is_exposed_on_detail(client, user):
    session = create_session(client)
    finalise_session(session["id"], make_outcome())
    assert client.get(f"{API}/practice/sessions/{session['id']}").json()["analysis_model"] == "test-model"


def test_user_b_gets_404_on_user_a_session(client, user):
    session = create_session(client)
    finalise_session(session["id"], make_outcome())

    other = TestClient(app)
    register(other, email="b@example.com")
    url = f"{API}/practice/sessions/{session['id']}"
    missing = other.get(f"{API}/practice/sessions/00000000-0000-0000-0000-000000000000")

    response = other.get(url)
    assert response.status_code == 404
    # Identical to a session that doesn't exist, so ids can't be probed.
    assert response.json() == missing.json()
    assert other.delete(url).status_code == 404
    assert client.get(url).status_code == 200
    assert other.get(f"{API}/practice/sessions").json() == {"items": [], "total": 0}


def test_malformed_session_id_is_404_not_a_database_error(client, user):
    response = client.get(f"{API}/practice/sessions/not-a-uuid")
    assert response.status_code == 404 and response.json()["code"] == "session_not_found"


def test_delete_session_keeps_rewards(client, user):
    session = create_session(client)
    finalise_session(session["id"], make_outcome())
    before = client.get(f"{API}/gamification/profile").json()
    assert before["xp"] > 0

    url = f"{API}/practice/sessions/{session['id']}"
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404

    after = client.get(f"{API}/gamification/profile").json()
    assert after["xp"] == before["xp"] and after["sparks"] == before["sparks"]
    assert after["stats"]["total_sessions"] == 1 and after["streak"]["current"] == 1
    assert client.get(f"{API}/gamification/badges").json()["items"][4]["unlocked"] is True
    assert client.get(f"{API}/gamification/activity").json()["items"]


def test_unknown_route_uses_the_uniform_error_body(client):
    response = client.get(f"{API}/nope")
    assert response.status_code == 404 and set(response.json()) == {"detail", "code"}


def test_health_runs_a_real_query(client):
    body = client.get(f"{API}/health").json()
    assert body["status"] == "ok" and body["database"] == "ok"
    assert body["live_provider"] == "mock" and body["coach_available"] is True and body["version"]


def test_health_reports_a_database_failure(client, monkeypatch):
    monkeypatch.setattr("app.api.routes.system.ping_database", lambda: False)
    response = client.get(f"{API}/health")
    assert response.status_code == 503
    assert response.json()["database"] == "error" and response.json()["status"] == "degraded"


def test_client_logs_are_sanitised_and_rate_limited(client, user, caplog):
    logger = logging.getLogger("spotlight.client")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="spotlight.client")
    try:
        response = client.post(
            f"{API}/client-logs",
            json={"level": "error", "message": "boom", "context": {"password": "hunter2", "page": "/x"}},
        )
    finally:
        logger.removeHandler(caplog.handler)
    assert response.status_code == 204
    assert "hunter2" not in caplog.text and "/x" in caplog.text

    statuses = [
        client.post(f"{API}/client-logs", json={"level": "info", "message": "m"}).status_code for _ in range(31)
    ]
    assert statuses[-1] == 429 and statuses[0] == 204


def test_client_logs_need_auth(client):
    assert client.post(f"{API}/client-logs", json={"level": "info", "message": "m"}).status_code == 401


def test_log_formatter_escapes_newlines_and_redacts():
    record = logging.LogRecord("spotlight.x", logging.INFO, __file__, 1, "evil\n2026-01-01 | INFO | forged", (), None)
    record.rid, record.uid = "ab12", "7"
    line = SafeFormatter().format(record)
    assert "\n" not in line and "\\n" in line
    assert "| INFO | spotlight.x | rid=ab12 uid=7 | evil" in line
    assert redact("key AQ.abc-DEF_123 done") == "key *** done"
    assert "secret" not in redact("postgresql+psycopg://user:secret@db:5432/x")


def test_access_log_has_method_path_status_and_user(client, user, caplog):
    logger = logging.getLogger("spotlight.access")
    logger.addHandler(caplog.handler)
    caplog.set_level(logging.INFO, logger="spotlight.access")
    try:
        response = client.get(f"{API}/auth/me")
    finally:
        logger.removeHandler(caplog.handler)
    assert response.headers["x-request-id"]
    assert f"GET {API}/auth/me 200" in caplog.text and user["id"] in caplog.text


def test_unwritable_log_dir_falls_back_to_stdout(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    settings = Settings(jwt_secret="x" * 40, database_url="postgresql+psycopg://u:p@h/d", log_dir=str(blocker / "logs"))
    try:
        configure_logging(settings)
        logging.getLogger("spotlight.test").info("still alive")
        output = capsys.readouterr().out
        assert "LOG_DIR is not writable" in output and "still alive" in output
    finally:
        configure_logging(get_settings())
