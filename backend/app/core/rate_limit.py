"""In-memory sliding-window rate limiter. Enough for the single uvicorn worker this app runs on."""
import threading
import time
from collections import deque
from collections.abc import Callable

_PURGE_EVERY_CALLS = 1000


class RateLimiter:
    """Allows `limit` hits per key within `window_seconds`.

    The lock is needed because sync route handlers run on a thread pool.
    """

    def __init__(self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key: str) -> bool:
        """Record an attempt. Returns False when the key is over its limit."""
        now = self._clock()
        with self._lock:
            self._calls += 1
            if self._calls % _PURGE_EVERY_CALLS == 0:
                self._purge(now)
            hits = self._hits.setdefault(key, deque())
            self._expire(hits, now)
            if len(hits) >= self._limit:
                return False
            hits.append(now)
            return True

    def reset(self, key: str) -> None:
        """Forget a key, for example after a successful login."""
        with self._lock:
            self._hits.pop(key, None)

    def clear(self) -> None:
        """Forget every key."""
        with self._lock:
            self._hits.clear()

    def _expire(self, hits: deque[float], now: float) -> None:
        while hits and now - hits[0] >= self._window:
            hits.popleft()

    def _purge(self, now: float) -> None:
        # Attackers can rotate keys freely, so idle ones must be dropped to keep memory bounded.
        for key in list(self._hits):
            self._expire(self._hits[key], now)
            if not self._hits[key]:
                del self._hits[key]


login_limiter = RateLimiter(limit=10, window_seconds=300)
client_log_limiter = RateLimiter(limit=30, window_seconds=60)
