"""The real coach backend, using the Gemini Live API and the Gemini analysis models.

The configuration here follows section 2 of the contract, which was verified against the real API.
"""
import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from app.core.config import Settings
from app.services.analysis.speech_analyzer import AnalysisError, AnalysisRequest, AnalysisResult, GeminiSpeechAnalyzer
from app.services.live.credentials import resolve_api_key
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

logger = logging.getLogger("spotlight.gemini")

_CONNECT_TIMEOUT_SECONDS = 15.0
_CONNECT_ATTEMPTS = 2
_CONNECT_RETRY_DELAY_SECONDS = 1.0
_CLOSE_TIMEOUT_SECONDS = 5.0
_INPUT_MIME_TYPE = "audio/pcm;rate=16000"


class ConnectionLost(Exception):
    """The Live connection ended without being asked to."""


def events_from_message(message: Any) -> list[LiveEvent]:
    """Translate one Live API message into provider events."""
    content = message.server_content
    if content is None:
        return []
    events: list[LiveEvent] = []
    if content.input_transcription and content.input_transcription.text:
        events.append(InputTranscript(content.input_transcription.text))
    if content.model_turn and content.model_turn.parts:
        for part in content.model_turn.parts:
            if part.inline_data and part.inline_data.data:
                events.append(AudioChunk(part.inline_data.data))
    if content.output_transcription and content.output_transcription.text:
        events.append(OutputTranscript(content.output_transcription.text))
    if content.interrupted:
        events.append(Interrupted())
    if content.turn_complete:
        events.append(TurnComplete())
    return events


class GeminiConnection(LiveConnection):
    """An open Live API session."""

    def __init__(self, context_manager: Any, session: Any) -> None:
        self._context_manager = context_manager
        self._session = session
        self._closed = False

    async def start_activity(self) -> None:
        await self._session.send_realtime_input(activity_start=types.ActivityStart())

    async def send_audio(self, pcm: bytes) -> None:
        await self._session.send_realtime_input(audio=types.Blob(data=pcm, mime_type=_INPUT_MIME_TYPE))

    async def end_activity(self) -> None:
        await self._session.send_realtime_input(activity_end=types.ActivityEnd())

    async def send_text(self, text: str) -> None:
        await self._session.send_realtime_input(text=text)

    async def events(self) -> AsyncIterator[LiveEvent]:
        # session.receive() stops after each turn, so it has to be restarted for the whole session.
        while True:
            received_any = False
            async for message in self._session.receive():
                received_any = True
                for event in events_from_message(message):
                    yield event
            if not received_any:
                # A receive() with nothing in it means the socket is finished. Without this check the
                # loop would spin forever, because nothing in it would ever wait.
                raise ConnectionLost()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            async with asyncio.timeout(_CLOSE_TIMEOUT_SECONDS):
                await self._context_manager.__aexit__(None, None, None)
        except Exception as exc:  # noqa: BLE001  we are leaving anyway, and closing must never raise
            logger.info("Live connection close error=%s", type(exc).__name__)


class GeminiProvider(LiveProvider):
    """Coach backend backed by the Gemini API."""

    name = "gemini"
    demo = False

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._clients: dict[str, genai.Client] = {}

    def is_available(self) -> bool:
        return resolve_api_key(self._settings) is not None

    def _client(self, user_id: str) -> genai.Client:
        # Reused per key because each client owns an HTTP connection pool.
        key = resolve_api_key(self._settings, user_id)
        if key is None:
            raise RuntimeError("no Gemini API key configured")
        if key not in self._clients:
            self._clients[key] = genai.Client(api_key=key)
        return self._clients[key]

    async def connect(self, config: LiveSessionConfig) -> LiveConnection:
        live_config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=config.system_instruction,
            speech_config={"voice_config": {"prebuilt_voice_config": {"voice_name": config.voice_name}}},
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Manual activity detection is what stops the coach interrupting a pause mid-speech.
            realtime_input_config={"automatic_activity_detection": {"disabled": True}},
        )
        client = self._client(config.user_id)
        attempt = 1
        while True:
            context_manager = client.aio.live.connect(model=self._settings.gemini_live_model, config=live_config)
            try:
                async with asyncio.timeout(_CONNECT_TIMEOUT_SECONDS):
                    session = await context_manager.__aenter__()
                return GeminiConnection(context_manager, session)
            except Exception as exc:
                logger.warning("Live connect failed attempt=%d error=%s", attempt, type(exc).__name__)
                if attempt == _CONNECT_ATTEMPTS:
                    raise
            attempt += 1
            await asyncio.sleep(_CONNECT_RETRY_DELAY_SECONDS)

    async def analyze(self, user_id: str, request: AnalysisRequest) -> AnalysisResult:
        try:
            client = self._client(user_id)
        except RuntimeError as exc:
            raise AnalysisError(str(exc)) from exc
        return await GeminiSpeechAnalyzer(client, self._settings.analysis_models).analyze(request)
