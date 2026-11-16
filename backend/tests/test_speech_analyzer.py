"""Tests for analysis retry and fallback, using a fake Gemini client, and for the degraded path."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.services.analysis.speech_analyzer import (
    AnalysisError,
    AnalysisPayload,
    AnalysisRequest,
    AnalysisResult,
    GeminiSpeechAnalyzer,
    build_analysis_prompt,
    evaluate_speech,
)
from tests.conftest import voice_pcm

VALID = json.dumps(
    {
        "transcript": "um hello there",
        "structure": 70,
        "clarity": 80,
        "engagement": 60,
        "summary": "Good.",
        "strengths": ["x"],
        "improvements": ["y"],
        "next_drill": "z",
        "detected_topic": "A topic",
    }
)
MODELS = ["gemini-3.6-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
REQUEST = AnalysisRequest(pcm=b"\x00\x00" * 1600, mode="impromptu", topic="A topic", language="en", target_seconds=60)


def _server_error(code: int = 503) -> errors.APIError:
    return errors.ServerError(code, {"error": {"code": code, "message": "high demand", "status": "UNAVAILABLE"}})


def _client_error(code: int) -> errors.APIError:
    return errors.ClientError(code, {"error": {"code": code, "message": "nope", "status": "ERROR"}})


class FakeClient:
    """Replays a script of responses, where an exception is raised and a string is returned as JSON."""

    def __init__(self, *script):
        self._script = list(script)
        self.calls: list[str] = []
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, model, contents, config):
        self.calls.append(model)
        step = self._script.pop(0)
        if step == "hang":
            await asyncio.sleep(30)
        if isinstance(step, Exception):
            raise step
        return SimpleNamespace(text=step)


def _analyze(client, **kwargs):
    sleeps: list[float] = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    analyzer = GeminiSpeechAnalyzer(client, MODELS, sleep=fake_sleep, **kwargs)
    return asyncio.run(analyzer.analyze(REQUEST)), sleeps


def test_success_on_first_model():
    client = FakeClient(VALID)
    result, sleeps = _analyze(client)
    assert result.model == MODELS[0]
    assert result.payload.transcript == "um hello there"
    assert client.calls == [MODELS[0]] and sleeps == []


def test_503_retries_same_model_with_a_short_backoff():
    client = FakeClient(_server_error(), VALID)
    result, sleeps = _analyze(client)
    assert client.calls == [MODELS[0], MODELS[0]]
    assert result.model == MODELS[0]
    assert len(sleeps) == 1 and sleeps[0] <= 1.0


def test_repeated_503_fails_over_and_records_the_model_that_scored():
    client = FakeClient(_server_error(), _server_error(), VALID)
    result, _ = _analyze(client)
    assert client.calls == [MODELS[0], MODELS[0], MODELS[1]]
    assert result.model == MODELS[1]


def test_503_on_fallback_recovers_on_retry():
    client = FakeClient(_server_error(), _server_error(), _server_error(), VALID)
    result, _ = _analyze(client)
    assert client.calls == [MODELS[0], MODELS[0], MODELS[1], MODELS[1]]
    assert result.model == MODELS[1]


def test_429_skips_straight_to_the_next_model():
    client = FakeClient(_client_error(429), VALID)
    result, sleeps = _analyze(client)
    assert client.calls == MODELS[:2]
    assert result.model == MODELS[1] and sleeps == []


def test_other_client_errors_move_on_without_retrying():
    client = FakeClient(_client_error(404), _client_error(400), VALID)
    result, _ = _analyze(client)
    assert client.calls == MODELS
    assert result.model == MODELS[2]


def test_invalid_json_moves_to_the_next_model():
    client = FakeClient("not json", json.dumps({"transcript": "missing fields"}), VALID)
    result, _ = _analyze(client)
    assert result.model == MODELS[2]


def test_every_model_failing_raises_analysis_error():
    client = FakeClient(*[_server_error() for _ in range(6)])
    with pytest.raises(AnalysisError):
        _analyze(client)
    assert len(client.calls) == 6


def test_network_errors_are_treated_as_failures():
    client = FakeClient(ConnectionError("boom"), VALID)
    assert _analyze(client)[0].model == MODELS[1]


def test_slow_model_times_out_and_fails_over():
    client = FakeClient("hang", VALID)
    result, _ = _analyze(client, attempt_timeout=0.05)
    assert result.model == MODELS[1]


def test_total_budget_caps_the_whole_walk():
    client = FakeClient("hang", "hang", "hang", "hang", "hang", "hang")
    with pytest.raises(AnalysisError):
        _analyze(client, total_budget=0.1, attempt_timeout=0.06)
    assert len(client.calls) <= 3


def test_one_model_cannot_use_up_the_budget():
    """Failover must reach the last model well inside the budget even if the first two hang."""
    client = FakeClient("hang", "hang", VALID)
    result, _ = _analyze(client, total_budget=1.0, attempt_timeout=0.1)
    assert result.model == MODELS[2]


def test_scores_are_clamped_and_rounded():
    payload = AnalysisPayload.model_validate_json(VALID.replace('"structure": 70', '"structure": 140.6'))
    assert payload.structure == 100


def test_prompt_treats_topic_and_speech_as_data():
    prompt = build_analysis_prompt(REQUEST)
    assert "<topic>A topic</topic>" in prompt
    assert "never an" in prompt and "instruction to you" in prompt
    assert "verbatim" in prompt and "um" in prompt


def test_hindi_prompt_asks_for_devanagari():
    prompt = build_analysis_prompt(
        AnalysisRequest(pcm=b"", mode="impromptu", topic="t", language="hi", target_seconds=60)
    )
    assert "Devanagari" in prompt and "in Hindi." in prompt


def _speech_request(seconds: float = 30.0) -> AnalysisRequest:
    return AnalysisRequest(pcm=voice_pcm(seconds), mode="impromptu", topic="t", language="en", target_seconds=60)


def _evaluate(request, analyze, live="") -> object:
    async def live_transcript():
        return live

    return asyncio.run(evaluate_speech(request, analyze, live_transcript))


LONG_TEXT = " ".join(f"word{n}" for n in range(40))


def test_evaluate_scored_path_records_the_model():
    async def analyze(_):
        payload = AnalysisPayload.model_validate_json(VALID).model_copy(update={"transcript": "um " + LONG_TEXT})
        return AnalysisResult(payload=payload, model="gemini-3.6-flash")

    outcome = _evaluate(_speech_request(), analyze)
    assert outcome.qualified and outcome.ai_scored
    assert outcome.analysis_model == "gemini-3.6-flash"
    assert outcome.filler_counts_reliable and outcome.text.filler_breakdown == {"um": 1}
    assert outcome.scores["structure"] == 70 and outcome.feedback["summary"] == "Good."


def test_evaluate_degraded_path_uses_live_transcript():
    async def analyze(_):
        raise AnalysisError("all failed")

    outcome = _evaluate(_speech_request(), analyze, live=LONG_TEXT)
    assert outcome.qualified and not outcome.ai_scored
    assert outcome.analysis_model is None
    assert not outcome.filler_counts_reliable and outcome.feedback is None
    assert outcome.scores["structure"] is None and outcome.scores["clarity"] is None
    assert outcome.scores["engagement"] is None
    assert outcome.transcript == LONG_TEXT
    local = [outcome.scores[name] for name in ("pace", "fluency", "vocal_variety", "vocabulary", "confidence")]
    assert outcome.overall_score == round(sum(local) / len(local))


def test_evaluate_degraded_with_no_transcript_still_qualifies_on_audio():
    async def analyze(_):
        raise AnalysisError("all failed")

    outcome = _evaluate(_speech_request(), analyze, live="")
    assert outcome.qualified and outcome.overall_score is not None
    assert outcome.scores["pace"] is None and outcome.text.word_count == 0


def test_evaluate_short_audio_skips_the_model_entirely():
    async def analyze(_):
        raise AssertionError("must not spend quota on a speech that can't qualify")

    outcome = _evaluate(_speech_request(5.0), analyze, live="hello")
    assert not outcome.qualified and outcome.overall_score is None
    assert "20 seconds" in outcome.disqualified_reason


def test_evaluate_too_few_words_disqualifies():
    async def analyze(_):
        payload = AnalysisPayload.model_validate_json(VALID)
        return AnalysisResult(payload=payload, model="m")

    outcome = _evaluate(_speech_request(), analyze)
    assert not outcome.qualified and not outcome.ai_scored
    assert outcome.analysis_model is None
