"""Free talk, where the speaker chooses the subject, and the suggested topics."""
import pytest

from app.main import app
from app.models.practice import PracticeSession
from app.core.database import session_scope
from app.services.analysis.speech_analyzer import AnalysisError, AnalysisRequest, build_analysis_prompt
from app.services.catalog import MODES
from app.services.live.mock import MockProvider
from app.services.live.prompts import build_system_instruction
from tests.conftest import API, register, voice_pcm
from tests.test_live_ws import _connect, _read, _read_until, _send, _stream

BODY = {"mode": "impromptu", "target_seconds": 60, "language": "en"}


@pytest.fixture
def user(client):
    return register(client)


def _create(client, **fields):
    return client.post(f"{API}/practice/sessions", json={**BODY, **fields})


def _give_speech_and_read_result(client, session_id):
    with _connect(client, session_id) as ws:
        assert _read(ws)["type"] == "ready"
        _send(ws, "speech_start")
        _stream(ws, voice_pcm(30))
        _send(ws, "speech_end")
        result = _read_until(ws, "session_result")[-1]["result"]
        _send(ws, "end_session")
    return result


def test_free_talk_needs_no_topic(client, user):
    response = _create(client, free_talk=True)
    assert response.status_code == 201 and response.json()["topic"] == "Free talk"
    with session_scope() as db:
        assert db.get(PracticeSession, response.json()["id"]).free_talk is True


def test_a_normal_session_still_needs_a_topic(client, user):
    assert _create(client).status_code == 422
    assert _create(client, free_talk=False).status_code == 422
    assert _create(client, topic="hi").status_code == 422


def test_a_normal_session_is_not_free_talk(client, user):
    response = _create(client, topic="Why practice matters")
    assert response.status_code == 201 and response.json()["topic"] == "Why practice matters"
    with session_scope() as db:
        assert db.get(PracticeSession, response.json()["id"]).free_talk is False


def test_free_talk_ignores_a_topic_sent_with_it(client, user):
    assert _create(client, free_talk=True, topic="Something else").json()["topic"] == "Free talk"


def test_the_scored_session_says_what_it_was_about(client, user):
    result = _give_speech_and_read_result(client, _create(client, free_talk=True).json()["id"])
    assert result["session"]["topic"] == "Free talk: Why practice matters"
    assert result["session"]["status"] == "completed" and result["session"]["feedback"]["summary"]
    assert all(value is not None for value in result["session"]["scores"].values())


def test_a_normal_session_keeps_its_own_topic_when_scored(client, user):
    result = _give_speech_and_read_result(client, _create(client, topic="My own topic").json()["id"])
    assert result["session"]["topic"] == "My own topic"


def test_free_talk_stays_named_when_scoring_fails(client, user):
    class FailingAnalysis(MockProvider):
        async def analyze(self, user_id, request):
            raise AnalysisError("down")

    app.state.live_provider = FailingAnalysis(reply_seconds=0.1, chunk_delay=0)
    result = _give_speech_and_read_result(client, _create(client, free_talk=True).json()["id"])
    assert result["session"]["topic"] == "Free talk" and result["session"]["ai_scored"] is False


def test_the_coach_is_told_there_is_no_set_topic():
    prompt = build_system_instruction("mentor", "impromptu", "Free talk", "hi", 120, free_talk=True)
    assert "<topic>" not in prompt and "no set topic" in prompt and "Always reply in Hindi" in prompt
    normal = build_system_instruction("mentor", "impromptu", "My topic", "hi", 120)
    assert "<topic>My topic</topic>" in normal and "no set topic" not in normal


def test_scoring_does_not_mark_free_talk_down_for_its_subject():
    fields = {"pcm": b"", "mode": "impromptu", "language": "en", "target_seconds": 60}
    free = build_analysis_prompt(AnalysisRequest(topic="Free talk", free_talk=True, **fields))
    assert "ignores the topic" not in free and "<topic>Free talk" not in free and "no set topic" in free
    normal = build_analysis_prompt(AnalysisRequest(topic="My topic", **fields))
    assert "ignores the topic" in normal and "<topic>My topic</topic>" in normal
    assert "detected_topic" in free and "detected_topic" in normal


@pytest.mark.parametrize("key", ["topics", "topics_hi"])
@pytest.mark.parametrize("mode", MODES, ids=lambda mode: mode["id"])
def test_every_mode_has_plenty_of_different_topics(mode, key):
    topics = mode[key]
    assert len(topics) >= 20 and len(set(topics)) == len(topics)
    assert all(3 <= len(topic) <= 200 for topic in topics)
    is_hindi = [any("ऀ" <= ch <= "ॿ" for ch in topic) for topic in topics]
    assert all(is_hindi) if key == "topics_hi" else not any(is_hindi)
