"""The interface between the session bridge and a coach backend (Gemini, or the mock)."""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.services.analysis.speech_analyzer import AnalysisRequest, AnalysisResult


@dataclass(frozen=True)
class AudioChunk:
    """Coach audio: PCM16 mono 24 kHz."""

    data: bytes


@dataclass(frozen=True)
class InputTranscript:
    """A fragment of what the user said."""

    text: str


@dataclass(frozen=True)
class OutputTranscript:
    """A fragment of the coach's words."""

    text: str


@dataclass(frozen=True)
class TurnComplete:
    """The coach finished a turn."""


@dataclass(frozen=True)
class Interrupted:
    """The coach's current turn was cut short."""


LiveEvent = AudioChunk | InputTranscript | OutputTranscript | TurnComplete | Interrupted


@dataclass(frozen=True)
class LiveSessionConfig:
    """What a provider needs to open a coaching session."""

    user_id: str
    coach_id: str
    voice_name: str
    system_instruction: str


class LiveConnection(ABC):
    """One open coaching session."""

    @abstractmethod
    async def start_activity(self) -> None:
        """Tell the coach the user has started speaking."""

    @abstractmethod
    async def send_audio(self, pcm: bytes) -> None:
        """Send PCM16 mono 16 kHz audio."""

    @abstractmethod
    async def end_activity(self) -> None:
        """Tell the coach the user has stopped, so it can reply."""

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Send a complete text turn, which the coach replies to out loud."""

    @abstractmethod
    def events(self) -> AsyncIterator[LiveEvent]:
        """Yield events across turns. The iterator only ends, or raises, when the connection is lost."""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection. Must be safe to call more than once and must not raise."""


class LiveProvider(ABC):
    """A coach backend."""

    name: str
    demo: bool

    @abstractmethod
    def is_available(self) -> bool:
        """Report whether this provider can serve sessions right now."""

    @abstractmethod
    async def connect(self, config: LiveSessionConfig) -> LiveConnection:
        """Open a coaching session. Raises if it can't."""

    @abstractmethod
    async def analyze(self, user_id: str, request: AnalysisRequest) -> AnalysisResult:
        """Score a speech. Raises AnalysisError on failure."""
