"""A coach backend with no network, for tests and demos. Scores and speech are canned, the tone is generated."""
import asyncio
from collections.abc import AsyncIterator

import numpy as np

from app.services.analysis.speech_analyzer import AnalysisPayload, AnalysisRequest, AnalysisResult, GrammarIssue
from app.services.live.provider import (
    AudioChunk,
    InputTranscript,
    Interrupted,
    LiveConnection,
    LiveEvent,
    LiveProvider,
    LiveSessionConfig,
    OutputTranscript,
    TurnComplete,
)

MOCK_MODEL = "mock-analysis"
_OUTPUT_RATE = 24000
_TONE_HZ = 440
_CHUNK_SECONDS = 0.1

MOCK_VERBATIM_TRANSCRIPT = (
    "Um, so today I want to talk about, like, why practice matters. Uh, I think most people, you know, "
    "avoid speaking in public because they are afraid of making mistakes. But basically every great speaker "
    "started out nervous. If you practise a little every day, um, you slowly build the confidence to stand "
    "up and say what you actually believe. So my advice is simple: start small, keep going, and be kind to "
    "yourself when it goes badly."
)
# Live transcription removes fillers, so the canned version does too. See section 2 of the contract.
MOCK_LIVE_TRANSCRIPT = (
    "So today I want to talk about why practice matters. Most people avoid speaking in public because they "
    "are afraid of making mistakes. Every great speaker started out nervous."
)
_COACH_SPEECH_REPLY = (
    "Nice work. Your strength was the clear message at the end. One thing to fix is the fillers in your "
    "opening. For your next drill, try pausing silently instead of saying um."
)
_COACH_FOLLOWUP_REPLY = "Good question. Pause, breathe, and restate your main point before moving on."


def generate_tone(seconds: float, rate: int = _OUTPUT_RATE, frequency: int = _TONE_HZ) -> bytes:
    """Generate a soft sine tone as PCM16 mono."""
    times = np.arange(int(seconds * rate)) / rate
    return (np.sin(2 * np.pi * frequency * times) * 6000).astype("<i2").tobytes()


class MockConnection(LiveConnection):
    """Replies to each finished turn with a transcript and a short tone."""

    def __init__(self, reply_seconds: float, chunk_delay: float) -> None:
        self._turns: asyncio.Queue[bool | None] = asyncio.Queue()
        self._reply_seconds = reply_seconds
        self._chunk_delay = chunk_delay
        self._interrupt = asyncio.Event()
        self._replying = False
        self._turn_count = 0

    async def start_activity(self) -> None:
        if self._replying:
            self._interrupt.set()

    async def send_audio(self, pcm: bytes) -> None:
        return None

    async def end_activity(self) -> None:
        self._turn_count += 1
        await self._turns.put(self._turn_count == 1)

    async def send_text(self, text: str) -> None:
        await self.end_activity()

    async def events(self) -> AsyncIterator[LiveEvent]:
        while (is_speech_turn := await self._turns.get()) is not None:
            self._replying = True
            self._interrupt.clear()
            if is_speech_turn:
                yield InputTranscript(MOCK_LIVE_TRANSCRIPT)
            yield OutputTranscript(_COACH_SPEECH_REPLY if is_speech_turn else _COACH_FOLLOWUP_REPLY)

            tone = generate_tone(self._reply_seconds)
            chunk_size = int(_OUTPUT_RATE * _CHUNK_SECONDS) * 2
            interrupted = False
            for start in range(0, len(tone), chunk_size):
                if self._interrupt.is_set():
                    interrupted = True
                    break
                yield AudioChunk(tone[start : start + chunk_size])
                await asyncio.sleep(self._chunk_delay)
            self._replying = False
            yield Interrupted() if interrupted else TurnComplete()

    async def close(self) -> None:
        await self._turns.put(None)


class MockProvider(LiveProvider):
    """Coach backend that needs neither a key nor a network."""

    name = "mock"
    demo = True

    def __init__(self, reply_seconds: float = 1.0, chunk_delay: float = 0.02, analysis_delay: float = 0.0) -> None:
        self._reply_seconds = reply_seconds
        self._chunk_delay = chunk_delay
        self._analysis_delay = analysis_delay

    def is_available(self) -> bool:
        return True

    async def connect(self, config: LiveSessionConfig) -> LiveConnection:
        return MockConnection(self._reply_seconds, self._chunk_delay)

    async def analyze(self, user_id: str, request: AnalysisRequest) -> AnalysisResult:
        if self._analysis_delay:
            await asyncio.sleep(self._analysis_delay)
        payload = AnalysisPayload(
            transcript=MOCK_VERBATIM_TRANSCRIPT,
            structure=72,
            clarity=78,
            engagement=66,
            summary="This is demo feedback. Your message was clear, but the opening was hesitant.",
            strengths=["A clear, memorable closing line."],
            improvements=["Replace the fillers in your opening with short silent pauses."],
            next_drill="Give the same speech again and pause silently wherever you would say um.",
            detected_topic="Why practice matters",
            grammar_score=84,
            grammar_issues=[
                GrammarIssue(
                    said="be kind to yourself when it goes badly",
                    better="be kind to yourself when it goes wrong",
                    why="This is demo feedback. 'Goes wrong' is the natural phrase for something that fails.",
                    type="word_choice",
                ),
            ],
        )
        return AnalysisResult(payload=payload, model=MOCK_MODEL)
