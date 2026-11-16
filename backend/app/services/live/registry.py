"""Tracks open live sessions, for the process-wide cost guard and the one-session-per-user rule.

An in-memory set is correct here because the app runs on a single uvicorn worker, and all access
happens on the event loop, so no lock is needed.
"""
from enum import Enum


class AcquireResult(Enum):
    """The outcome of asking for a live slot."""

    OK = "ok"
    USER_BUSY = "user_busy"
    FULL = "full"


class LiveRegistry:
    """The set of users currently connected to a coach."""

    def __init__(self, max_sessions: int) -> None:
        self._max_sessions = max_sessions
        self._active: set[str] = set()

    def acquire(self, user_id: str) -> AcquireResult:
        """Claim a slot for a user."""
        if user_id in self._active:
            return AcquireResult.USER_BUSY
        if len(self._active) >= self._max_sessions:
            return AcquireResult.FULL
        self._active.add(user_id)
        return AcquireResult.OK

    def release(self, user_id: str) -> None:
        """Give a user's slot back."""
        self._active.discard(user_id)
