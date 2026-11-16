"""The WebSocket session state machine: connects a browser to a coach and runs scoring.

Four tasks run while connected, so that no direction can hold up another:

- client pump: reads the browser's frames. It never waits on the provider, only on a queue.
- provider sender: drains that queue to the provider, so slow sends can't stop us reading the browser.
- provider pump: forwards coach events to the browser, including while the user is sending audio.
- watchdog: enforces the speech and session time limits.

Scoring runs as a separate background task, outside the lifetime of the socket, because a client that
disconnects right after `speech_end` must still get its session scored and saved.
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import date
from enum import Enum
from functools import partial
from typing import Any

from fastapi import WebSocket
from fastapi.concurrency import run_in_threadpool

from app.core.config import Settings
from app.core.timeutils import utcnow
from app.services.analysis.audio_metrics import BYTES_PER_SECOND
from app.services.analysis.speech_analyzer import analysis_budget_seconds, AnalysisRequest, evaluate_speech
from app.services.catalog import COACHES
from app.services.gamification.rewards import finalise_session
from app.services.live import usage
from app.services.live.prompts import build_handoff_message, build_system_instruction
from app.services.live.provider import (
    AudioChunk,
    InputTranscript,
    Interrupted,
    LiveConnection,
    LiveProvider,
    LiveSessionConfig,
    OutputTranscript,
    TurnComplete,
)

logger = logging.getLogger("spotlight.live")

MAX_FRAME_BYTES = 64 * 1024
_MAX_TEXT_FRAME_CHARS = 4096
_MAX_QUEUED_AUDIO_FRAMES = 256
_WATCHDOG_TICK_SECONDS = 0.25
# Gemini closes a session with 1008 after 120 s without client audio. Measured on 2026-11-05: WebSocket
# pings don't reset that timer, while a short burst of silence does and doesn't trigger a coach reply.
_KEEPALIVE_SECONDS = 30.0
_KEEPALIVE_FRAME = bytes(3200)  # 100 ms of silence at 16 kHz.
_SEND_TIMEOUT_SECONDS = 10.0
_MAX_ERROR_CHARS = 240
_SECRET_PATTERN = re.compile(r"(AQ\.|AIza)[\w-]+|(key=)[^&\s]+")
# Input transcription can arrive only at the end of the turn, shortly after activity_end.
_LIVE_TRANSCRIPT_WAIT_SECONDS = 5.0
_DRAIN_TIMEOUT_SECONDS = 310.0
# Gemini closes a session with 1008 about 481 s after connecting if the model hasn't replied yet. Measured on
# 2026-11-05: it happens mid-speech and on an idle session, with no go_away first, and context compression and
# session resumption don't change it. A 7:30 speech got its reply, and that session was still open at 13:30.
# So past this point the coach is let go, the speech keeps recording, and a fresh session gives the feedback.
_LIVE_UNANSWERED_LIMIT_SECONDS = 420.0

CLOSE_NORMAL = 1000
CLOSE_INTERNAL_ERROR = 1011
CLOSE_COACH_UNAVAILABLE = 4503

_background_tasks: set[asyncio.Task] = set()


def _describe_error(exc: Exception) -> str:
    """Describe a provider failure for the logs, with anything key-shaped removed.

    The close reason is what tells quota, inactivity and outages apart, so the type alone isn't enough.
    """
    return _SECRET_PATTERN.sub("***", f"{type(exc).__name__}: {exc}")[:_MAX_ERROR_CHARS]


def _spawn_background(coroutine: Any) -> asyncio.Task:
    # The event loop only keeps weak references to tasks, so without this set one could be collected
    # mid-flight, losing a user's scored session.
    task = asyncio.create_task(coroutine)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def drain_background_tasks() -> None:
    """Let in-flight scoring finish during shutdown, up to the analysis time budget."""
    if _background_tasks:
        await asyncio.wait(_background_tasks, timeout=_DRAIN_TIMEOUT_SECONDS)


@dataclass(frozen=True)
class BridgeSession:
    """The session facts the bridge needs."""

    session_id: str
    user_id: str
    mode: str
    topic: str
    language: str
    coach_id: str
    target_seconds: int
    local_date: date
    free_talk: bool = False
    # Set on a second take: the grammar slips flagged last time, as (said, better). Empty if there were none.
    retake_slips: tuple[tuple[str, str], ...] | None = None


class _State(Enum):
    IDLE = "idle"
    SPEECH = "speech"
    POST_SPEECH = "post_speech"
    FOLLOWUP = "followup"


class _StopReason(Enum):
    CLIENT_GONE = "client_gone"
    END_SESSION = "end_session"
    TIME_LIMIT = "time_limit"
    PROVIDER_FAILED = "provider_failed"
    INTERNAL_ERROR = "internal_error"


class LiveBridge:
    """Runs one live session from connection to close."""

    def __init__(
        self,
        websocket: WebSocket,
        session: BridgeSession,
        provider: LiveProvider,
        settings: Settings,
        budget_seconds: float,
    ) -> None:
        self._ws = websocket
        self._session = session
        self._provider = provider
        self._settings = settings
        self._session_limit = min(settings.live_max_session_seconds, budget_seconds)
        self._max_speech_bytes = settings.max_speech_seconds * BYTES_PER_SECOND

        self._state = _State.IDLE
        self._connection: LiveConnection | None = None
        self._provider_alive = False
        self._client_connected = True
        self._send_lock = asyncio.Lock()
        self._outbound: asyncio.Queue[tuple[str, bytes | None]] = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._stop_reason: _StopReason | None = None

        self._speech_pcm = bytearray()
        self._received_audio_bytes = 0
        self._speech_started_at: float | None = None
        self._speech_ended = False
        self._finalise_task: asyncio.Task | None = None
        self._frame_error_sent = False

        self._live_transcript: list[str] = []
        self._coach_transcript: list[str] = []
        self._speech_turn_done = asyncio.Event()
        self._speech_turn_open = True
        self._connected_at = time.monotonic()
        # True when the coach didn't hear the speech and a fresh session must take over when it ends.
        self._coach_released = False
        self._coach_tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        """Run the session until it stops. The socket has already been accepted."""
        try:
            if await self._connect():
                await self._send_json(
                    {
                        "type": "ready",
                        # A daily limit that is nearly used up can end the take sooner than the usual maximum.
                        "max_speech_seconds": int(min(self._settings.max_speech_seconds, self._session_limit)),
                        "target_seconds": self._session.target_seconds,
                        "demo": self._provider.demo,
                    }
                )
                await self._pump_until_stopped()
        finally:
            # A separate task, because a cancelled handler can no longer await anything itself, and
            # skipping this would lose the time used and leave the session active.
            await asyncio.shield(_spawn_background(self._wind_down()))

    async def _wind_down(self) -> None:
        await self._close_connection()
        await self._record_close()

    def _live_config(self) -> LiveSessionConfig:
        session = self._session
        return LiveSessionConfig(
            user_id=session.user_id,
            coach_id=session.coach_id,
            voice_name=COACHES[session.coach_id].voice,
            system_instruction=build_system_instruction(
                session.coach_id,
                session.mode,
                session.topic,
                session.language,
                session.target_seconds,
                session.free_talk,
                retake_slips=session.retake_slips,
            ),
        )

    async def _connect(self) -> bool:
        session = self._session
        try:
            self._connection = await self._provider.connect(self._live_config())
        except Exception as exc:  # noqa: BLE001  any connect failure gets the same response
            logger.error("coach connect failed session=%s error=%s", session.session_id, _describe_error(exc))
            await self._send_error("coach_unavailable", "The coach couldn't connect. Please try again.", fatal=True)
            await self._close_socket(CLOSE_COACH_UNAVAILABLE)
            return False
        self._provider_alive = True
        logger.info("live session connected session=%s provider=%s", session.session_id, self._provider.name)
        return True

    async def _pump_until_stopped(self) -> None:
        pumps = [
            asyncio.create_task(self._guarded(self._client_pump)),
            asyncio.create_task(self._guarded(self._watchdog)),
            asyncio.create_task(self._guarded(self._keepalive)),
        ]
        self._start_coach_pumps()
        try:
            await self._stop_event.wait()
        finally:
            for pump in pumps:
                pump.cancel()
            await asyncio.gather(*pumps, return_exceptions=True)
            await self._stop_coach_pumps()

        reason = self._stop_reason
        # Closing now ends the coach's billing even if scoring still has a while to run.
        await self._close_connection()
        self._speech_turn_done.set()

        if reason is _StopReason.TIME_LIMIT and self._state is _State.SPEECH:
            await self._end_speech()

        if reason is _StopReason.CLIENT_GONE:
            logger.info("client disconnected session=%s speech_ended=%s", self._session.session_id, self._speech_ended)
            return

        if self._finalise_task is not None:
            # Shielded so a cancelled handler can't take the scoring down with it.
            await asyncio.shield(self._finalise_task)
        await self._send_closing_frames(reason)

    async def _send_closing_frames(self, reason: _StopReason | None) -> None:
        if reason is _StopReason.TIME_LIMIT:
            await self._send_error("session_time_limit", "This session reached its time limit.", fatal=True)
            await self._close_socket(CLOSE_NORMAL)
        elif reason is _StopReason.PROVIDER_FAILED:
            await self._send_error("coach_unavailable", "The connection to the coach was lost.", fatal=True)
            await self._close_socket(CLOSE_NORMAL if self._speech_ended else CLOSE_COACH_UNAVAILABLE)
        elif reason is _StopReason.INTERNAL_ERROR:
            await self._send_error("internal_error", "Something went wrong on our side.", fatal=True)
            await self._close_socket(CLOSE_INTERNAL_ERROR)
        else:
            await self._close_socket(CLOSE_NORMAL)

    def _start_coach_pumps(self) -> None:
        self._coach_tasks = [
            asyncio.create_task(self._guarded(self._provider_sender)),
            asyncio.create_task(self._guarded(self._provider_pump)),
        ]

    async def _stop_coach_pumps(self) -> None:
        tasks, self._coach_tasks = self._coach_tasks, []
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    def _stop(self, reason: _StopReason) -> None:
        # The first reason wins, because later ones are usually consequences of it.
        if self._stop_reason is None:
            self._stop_reason = reason
        self._stop_event.set()

    async def _guarded(self, pump: Any) -> None:
        try:
            await pump()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("live pump %s failed session=%s", pump.__name__, self._session.session_id)
            self._stop(_StopReason.INTERNAL_ERROR)

    # Client to provider

    async def _client_pump(self) -> None:
        while True:
            message = await self._ws.receive()
            if message["type"] == "websocket.disconnect":
                self._client_connected = False
                self._stop(_StopReason.CLIENT_GONE)
                return
            if message.get("bytes") is not None:
                await self._on_audio_frame(message["bytes"])
            elif message.get("text") is not None:
                await self._on_text_frame(message["text"])

    async def _on_audio_frame(self, frame: bytes) -> None:
        if len(frame) > MAX_FRAME_BYTES or len(frame) % 2 != 0:
            # Reported once only: a broken client would otherwise get an error per frame.
            if not self._frame_error_sent:
                self._frame_error_sent = True
                await self._send_error(
                    "invalid_audio_frame", "Audio frames must be even length and at most 64 KB.", fatal=False
                )
            return

        if self._state is _State.FOLLOWUP:
            self._enqueue_audio(frame)
        elif self._state is _State.SPEECH:
            room = self._max_speech_bytes - len(self._speech_pcm)
            accepted = frame[:room]
            self._speech_pcm.extend(accepted)
            self._received_audio_bytes += len(accepted)
            self._enqueue_audio(accepted)
            if len(self._speech_pcm) >= self._max_speech_bytes:
                await self._auto_end_speech()

    def _enqueue_audio(self, frame: bytes) -> None:
        # If the provider stalls, dropping the coach's copy is fine: the graded copy is already buffered.
        if frame and self._provider_alive and self._outbound.qsize() < _MAX_QUEUED_AUDIO_FRAMES:
            self._outbound.put_nowait(("audio", frame))

    def _enqueue_control(self, kind: str) -> None:
        if self._provider_alive:
            self._outbound.put_nowait((kind, None))

    async def _on_text_frame(self, text: str) -> None:
        try:
            if len(text) > _MAX_TEXT_FRAME_CHARS:
                raise ValueError("frame too long")
            message_type = json.loads(text)["type"]
        except (ValueError, KeyError, TypeError):
            await self._send_error("bad_message", "That message couldn't be read.", fatal=False)
            return

        handlers = {
            "speech_start": self._on_speech_start,
            "speech_end": self._on_speech_end,
            "followup_start": self._on_followup_start,
            "followup_end": self._on_followup_end,
            "end_session": self._on_end_session,
        }
        handler = handlers.get(message_type) if isinstance(message_type, str) else None
        if handler is None:
            await self._send_error("bad_message", "Unknown message type.", fatal=False)
            return
        await handler()

    async def _invalid_state(self, action: str) -> None:
        await self._send_error("invalid_state", f"{action} isn't allowed right now.", fatal=False)

    async def _on_speech_start(self) -> None:
        if self._state is not _State.IDLE:
            await self._invalid_state("speech_start")
            return
        self._state = _State.SPEECH
        self._speech_started_at = time.monotonic()
        self._enqueue_control("activity_start")

    async def _on_speech_end(self) -> None:
        if self._state is not _State.SPEECH:
            await self._invalid_state("speech_end")
            return
        await self._end_speech()

    async def _on_followup_start(self) -> None:
        if self._state is not _State.POST_SPEECH:
            await self._invalid_state("followup_start")
            return
        if not self._provider_alive:
            await self._send_error("coach_unavailable", "The coach is no longer connected.", fatal=False)
            return
        self._state = _State.FOLLOWUP
        self._close_speech_turn()
        await self._send_json({"type": "interrupted"})
        self._enqueue_control("activity_start")

    async def _on_followup_end(self) -> None:
        if self._state is not _State.FOLLOWUP:
            await self._invalid_state("followup_end")
            return
        self._state = _State.POST_SPEECH
        self._enqueue_control("activity_end")

    async def _on_end_session(self) -> None:
        self._stop(_StopReason.END_SESSION)

    async def _auto_end_speech(self) -> None:
        await self._send_json({"type": "speech_limit_reached"})
        await self._end_speech()

    async def _end_speech(self) -> None:
        self._state = _State.POST_SPEECH
        self._speech_ended = True
        self._enqueue_control("activity_end")
        pcm = bytes(self._speech_pcm)
        self._speech_pcm = bytearray()
        self._finalise_task = _spawn_background(self._finalise(pcm))

    async def _provider_sender(self) -> None:
        connection = self._connection
        try:
            while True:
                kind, payload = await self._outbound.get()
                if kind == "audio":
                    await connection.send_audio(payload)
                elif kind == "activity_start":
                    await connection.start_activity()
                else:
                    await connection.end_activity()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001  any send failure means the connection is gone
            logger.warning("coach send failed session=%s error=%s", self._session.session_id, _describe_error(exc))
            await self._on_provider_lost()

    # Provider to client

    async def _provider_pump(self) -> None:
        try:
            async for event in self._connection.events():
                await self._on_provider_event(event)
            logger.warning("coach stream ended session=%s", self._session.session_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001  any receive failure means the connection is gone
            logger.warning("coach receive failed session=%s error=%s", self._session.session_id, _describe_error(exc))
        await self._on_provider_lost()

    async def _on_provider_event(self, event: Any) -> None:
        if isinstance(event, AudioChunk):
            # While the user is talking, leftover coach audio would just talk over them.
            if self._state not in (_State.SPEECH, _State.FOLLOWUP):
                await self._send_bytes(event.data)
        elif isinstance(event, InputTranscript):
            if self._speech_turn_open:
                self._live_transcript.append(event.text)
            await self._send_json({"type": "input_transcript", "text": event.text})
        elif isinstance(event, OutputTranscript):
            self._coach_transcript.append(event.text)
            await self._send_json({"type": "output_transcript", "text": event.text})
        elif isinstance(event, TurnComplete):
            if self._speech_ended:
                self._close_speech_turn()
            self._coach_transcript.append("\n")
            await self._send_json({"type": "turn_complete"})
        elif isinstance(event, Interrupted):
            await self._send_json({"type": "interrupted"})

    def _close_speech_turn(self) -> None:
        # Later input transcripts belong to follow-ups, which must not be mixed into the graded speech.
        self._speech_turn_open = False
        self._speech_turn_done.set()

    async def _on_provider_lost(self) -> None:
        if not self._provider_alive:
            return
        self._provider_alive = False
        self._speech_turn_done.set()
        if self._state is _State.SPEECH:
            # The speech is still recording, and a fresh coach can take over when it ends.
            logger.info("coach lost mid-speech session=%s", self._session.session_id)
            self._coach_released = True
            return
        if self._state is _State.FOLLOWUP:
            self._state = _State.POST_SPEECH

        scoring_finished = self._finalise_task is not None and self._finalise_task.done()
        if self._state is _State.IDLE or scoring_finished:
            self._stop(_StopReason.PROVIDER_FAILED)
            return
        # The speech is buffered here, so it can still be scored without the coach.
        await self._send_error(
            "coach_disconnected", "The coach disconnected, but your speech will still be scored.", fatal=False
        )

    # Limits

    async def _watchdog(self) -> None:
        while True:
            await asyncio.sleep(_WATCHDOG_TICK_SECONDS)
            now = time.monotonic()
            if now - self._connected_at >= self._session_limit:
                logger.info("session time limit reached session=%s", self._session.session_id)
                self._stop(_StopReason.TIME_LIMIT)
                return
            if (
                self._provider_alive
                and self._state in (_State.IDLE, _State.SPEECH)
                and now - self._connected_at >= _LIVE_UNANSWERED_LIMIT_SECONDS
            ):
                await self._release_coach()
            if (
                self._state is _State.SPEECH
                and now - self._speech_started_at >= self._settings.max_speech_seconds
            ):
                await self._auto_end_speech()

    async def _release_coach(self) -> None:
        """Close the coach before Gemini does. Nothing is lost, because the graded speech is buffered here."""
        logger.info("coach released before the live limit session=%s", self._session.session_id)
        self._provider_alive = False
        self._coach_released = True
        self._speech_turn_done.set()
        await self._stop_coach_pumps()
        while not self._outbound.empty():
            self._outbound.get_nowait()
        await self._connection.close()

    async def _hand_off_to_fresh_coach(self, transcript: str) -> None:
        """Have a new Live session give the spoken feedback, from the transcript of the speech it didn't hear."""
        session_id = self._session.session_id
        if not transcript.strip():
            logger.info("no transcript for the fresh coach session=%s", session_id)
            return
        await self._stop_coach_pumps()
        await self._connection.close()
        try:
            connection = await self._provider.connect(self._live_config())
        except Exception as exc:  # noqa: BLE001  the score is already safe, so losing the voice must not take it down
            logger.warning("fresh coach connect failed session=%s error=%s", session_id, _describe_error(exc))
            return
        if self._stop_event.is_set():
            await connection.close()
            return
        self._connection = connection
        self._provider_alive = True
        self._coach_released = False
        self._start_coach_pumps()
        try:
            await connection.send_text(build_handoff_message(transcript))
        except Exception as exc:  # noqa: BLE001  same as above
            logger.warning("fresh coach send failed session=%s error=%s", session_id, _describe_error(exc))
            await self._stop_coach_pumps()
            await self._close_connection()
            return
        logger.info("fresh coach connected session=%s", session_id)

    async def _keepalive(self) -> None:
        # Users pause on the start screen and read their scorecard before asking a follow-up, and the
        # coach must still be there when they come back. While they talk, their own audio does this job.
        while True:
            await asyncio.sleep(_KEEPALIVE_SECONDS)
            if self._state in (_State.IDLE, _State.POST_SPEECH):
                self._enqueue_audio(_KEEPALIVE_FRAME)

    # Scoring

    async def _await_live_transcript(self) -> str:
        try:
            async with asyncio.timeout(_LIVE_TRANSCRIPT_WAIT_SECONDS):
                await self._speech_turn_done.wait()
        except TimeoutError:
            pass
        return " ".join("".join(self._live_transcript).split())

    async def _finalise(self, pcm: bytes) -> None:
        session = self._session
        await self._send_json({"type": "analysis_started", "budget_seconds": analysis_budget_seconds(len(pcm))})
        request = AnalysisRequest(
            pcm=pcm,
            mode=session.mode,
            topic=session.topic,
            language=session.language,
            target_seconds=session.target_seconds,
            free_talk=session.free_talk,
        )
        try:
            outcome = await evaluate_speech(
                request, partial(self._provider.analyze, session.user_id), self._await_live_transcript
            )
            result = await run_in_threadpool(finalise_session, session.session_id, outcome, utcnow())
        except Exception:
            logger.exception("scoring failed session=%s", session.session_id)
            await run_in_threadpool(usage.abandon_session, session.session_id)
            await self._send_error("scoring_failed", "We couldn't score this session.", fatal=False)
        else:
            if result is not None:
                # The coach may still be talking, so its transcript so far is all that exists to send.
                result["session"]["coach_transcript"] = self._coach_transcript_text()
                await self._send_json({"type": "session_result", "result": result})
            if self._coach_released and not self._stop_event.is_set():
                await self._hand_off_to_fresh_coach(outcome.transcript)
        # With the coach gone and scoring done, nothing is left for this socket to do.
        if not self._provider_alive:
            self._stop(_StopReason.PROVIDER_FAILED)

    def _coach_transcript_text(self) -> str:
        return "\n".join(" ".join(line.split()) for line in "".join(self._coach_transcript).splitlines()).strip()

    # Closing

    async def _close_connection(self) -> None:
        self._provider_alive = False
        if self._connection is not None:
            await self._connection.close()

    async def _record_close(self) -> None:
        connected = time.monotonic() - self._connected_at
        # Audio can arrive faster than real time, and the larger number is what the coach actually cost.
        live_seconds = round(max(connected, self._received_audio_bytes / BYTES_PER_SECOND), 1)
        session = self._session
        try:
            await run_in_threadpool(
                usage.close_session,
                session.session_id,
                session.user_id,
                session.local_date,
                live_seconds,
                self._coach_transcript_text(),
                abandon=not self._speech_ended,
            )
        except Exception:
            logger.exception("failed to record session close session=%s", session.session_id)

    # Sending. Failures are swallowed because a vanished client must never break the session's bookkeeping.

    async def _send_json(self, payload: dict[str, Any]) -> None:
        await self._send({"text": json.dumps(payload, ensure_ascii=False)})

    async def _send_bytes(self, data: bytes) -> None:
        await self._send({"bytes": data})

    async def _send_error(self, code: str, message: str, fatal: bool) -> None:
        await self._send_json({"type": "error", "code": code, "message": message, "fatal": fatal})

    async def _send(self, fields: dict[str, Any]) -> None:
        if not self._client_connected:
            return
        try:
            # The lock keeps frames from different tasks whole. The timeout stops a stalled client
            # from holding up the provider pump and the session result forever.
            async with asyncio.timeout(_SEND_TIMEOUT_SECONDS):
                async with self._send_lock:
                    await self._ws.send({"type": "websocket.send", **fields})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001  Starlette, uvicorn and timeouts all raise different types
            logger.info("client send failed session=%s error=%s", self._session.session_id, type(exc).__name__)
            self._client_connected = False

    async def _close_socket(self, code: int) -> None:
        if not self._client_connected:
            return
        self._client_connected = False
        try:
            await self._ws.close(code)
        except Exception as exc:  # noqa: BLE001  the socket may already be gone
            logger.info("socket close failed session=%s error=%s", self._session.session_id, type(exc).__name__)
