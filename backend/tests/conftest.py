"""Test setup: a real Postgres database, migrated by the real Alembic migration.

TEST_DATABASE_URL is separate from DATABASE_URL on purpose. These fixtures erase the database, so a
stray run inside the app container must not be able to reach real data.
"""
import os
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

_url = os.environ.get("TEST_DATABASE_URL", "")
if not _url.rsplit("/", 1)[-1].endswith("_test"):
    pytest.exit("Set TEST_DATABASE_URL to a throwaway database whose name ends in _test.", returncode=2)

os.environ.update(
    DATABASE_URL=_url,
    JWT_SECRET="test-secret-test-secret-test-secret-1234",
    LIVE_PROVIDER="mock",
    GEMINI_API_KEY="",
    LOG_DIR=tempfile.mkdtemp(prefix="spotlight-test-logs-"),
    ALLOWED_ORIGINS="http://localhost:1201,http://127.0.0.1:1201",
    DAILY_LIVE_SECONDS_PER_USER="1800",
    MAX_CONCURRENT_LIVE_SESSIONS="10",
    LIVE_MAX_SESSION_SECONDS="600",
    MAX_SPEECH_SECONDS="300",
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402, F401
from app.core.database import Base, get_engine, session_scope  # noqa: E402
from app.core.rate_limit import client_log_limiter, login_limiter  # noqa: E402
from app.main import app  # noqa: E402
from app.services.analysis.audio_metrics import AudioMetrics  # noqa: E402
from app.services.analysis.speech_analyzer import SpeechOutcome  # noqa: E402
from app.services.analysis.text_metrics import compute_text_metrics  # noqa: E402

ORIGIN = {"origin": "http://localhost:1201"}
API = "/api/v1"
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def alembic_config() -> Config:
    """Return an Alembic config that works from any working directory."""
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    with get_engine().begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")


@pytest.fixture(autouse=True)
def _clean_state(_migrated_database):
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    with get_engine().begin() as connection:
        connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    login_limiter.clear()
    client_log_limiter.clear()


@pytest.fixture
def client():
    """A client with the app's lifespan running, so background tasks and WebSockets share one loop."""
    with TestClient(app) as test_client:
        yield test_client


def register(
    test_client: TestClient, email: str = "a@example.com", timezone: str = "UTC", password: str = "password123"
) -> dict:
    """Register a user, leaving the client logged in."""
    response = test_client.post(
        f"{API}/auth/register",
        json={"email": email, "password": password, "display_name": "Asha", "timezone": timezone},
    )
    assert response.status_code == 201, response.text
    return response.json()["user"]


def create_session(test_client: TestClient, mode: str = "impromptu", language: str = "en") -> dict:
    """Create a practice session through the API."""
    response = test_client.post(
        f"{API}/practice/sessions",
        json={"mode": mode, "topic": "Why practice matters", "target_seconds": 60, "language": language},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def user(client):
    """A logged-in user on the default client."""
    return register(client)


def voice_pcm(seconds: float = 30.0) -> bytes:
    """Generate voice-like PCM: a tone whose loudness changes every half second."""
    rate = 16000
    times = np.arange(int(seconds * rate)) / rate
    envelope = 5000 + 4000 * np.sign(np.sin(2 * np.pi * times))
    return (np.sin(2 * np.pi * 220 * times) * envelope).astype("<i2").tobytes()


def make_outcome(
    seconds: float = 120.0,
    score: int = 75,
    transcript: str | None = None,
    qualified: bool = True,
    ai_scored: bool = True,
) -> SpeechOutcome:
    """Build a scored outcome directly, for tests that exercise the reward transaction."""
    words = transcript if transcript is not None else " ".join(f"word{n}" for n in range(280))
    scores = {
        "pace": 90,
        "fluency": 70,
        "vocal_variety": 60,
        "vocabulary": 65,
        "confidence": 80,
        "structure": score if ai_scored else None,
        "clarity": score if ai_scored else None,
        "engagement": score if ai_scored else None,
    }
    return SpeechOutcome(
        qualified=qualified,
        disqualified_reason=None if qualified else "Too short.",
        audio=AudioMetrics(
            speaking_seconds=seconds, pause_count=2, longest_pause_seconds=1.2, pause_ratio=0.1, volume_variation=0.5
        ),
        text=compute_text_metrics(words, seconds),
        transcript=words,
        scores=scores,
        overall_score=score if qualified else None,
        ai_scored=ai_scored,
        analysis_model="test-model" if ai_scored else None,
        filler_counts_reliable=ai_scored,
        feedback={"summary": "s", "strengths": ["a"], "improvements": ["b"], "next_drill": "d"} if ai_scored else None,
    )


def wait_for_status(test_client: TestClient, session_id: str, wanted: str, timeout: float = 10.0) -> dict:
    """Poll a session until it reaches a status, for work that continues after a disconnect."""
    deadline = time.monotonic() + timeout
    while True:
        body = test_client.get(f"{API}/practice/sessions/{session_id}").json()
        if body["status"] == wanted:
            return body
        if time.monotonic() > deadline:
            raise AssertionError(f"session stayed {body['status']}, wanted {wanted}")
        time.sleep(0.05)


def run_sql(statement: str, **params) -> None:
    """Run a raw statement, for arranging test data."""
    with session_scope() as db:
        db.execute(text(statement), params)
