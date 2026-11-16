"""Rotating-file logging, with request context and protection against log injection.

The request context is one mutable object held in a contextvar. FastAPI runs sync dependencies and
handlers in separate copies of the context, so a plain `uid` contextvar set during authentication
would be invisible to the handler and to the access log. A shared object is visible to all of them.
"""
import logging
import logging.handlers
import re
import sys
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings

_MAX_BYTES = 10 * 1024 * 1024
_BACKUPS = 5
_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | rid=%(rid)s uid=%(uid)s | %(message)s"

# Defence in depth: nothing should log these, but an exception message could carry one by accident.
_SECRET_PATTERNS = (
    (re.compile(r"AQ\.[A-Za-z0-9_-]+"), "***"),
    (re.compile(r"AIza[A-Za-z0-9_-]{20,}"), "***"),
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "***"),
    (re.compile(r"(postgresql(?:\+\w+)?://[^:/@\s]+:)[^@\s]+(@)"), r"\1***\2"),
)


@dataclass
class RequestContext:
    """Identifiers attached to every log line produced while handling one request."""

    request_id: str = "-"
    user_id: str = "-"


_context: ContextVar[RequestContext | None] = ContextVar("spotlight_request_context", default=None)


def new_request_context() -> RequestContext:
    """Start a fresh context for a new request or WebSocket."""
    context = RequestContext(request_id=uuid.uuid4().hex[:8])
    _context.set(context)
    return context


def bind_user(user_id: str) -> None:
    """Record the authenticated user on the current request context."""
    context = _context.get()
    if context is not None:
        context.user_id = user_id


def redact(text: str) -> str:
    """Remove anything that looks like a credential."""
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = _context.get() or RequestContext()
        record.rid = context.request_id
        record.uid = context.user_id
        return True


class SafeFormatter(logging.Formatter):
    """Formats one record as exactly one line, so user input can't forge a log entry."""

    converter = time.gmtime

    def __init__(self) -> None:
        super().__init__(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        line = redact(super().format(record))
        return line.replace("\r", "\\r").replace("\n", "\\n")


def _file_handler(directory: Path, name: str, level: int) -> logging.Handler:
    handler = logging.handlers.RotatingFileHandler(
        directory / name, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    handler.setLevel(level)
    return handler


def configure_logging(settings: Settings) -> None:
    """Install the handlers. An unwritable LOG_DIR falls back to stdout instead of stopping the app."""
    formatter = SafeFormatter()
    context_filter = _ContextFilter()
    console = logging.StreamHandler(sys.stdout)
    root_handlers: list[logging.Handler] = [console]
    access_handlers: list[logging.Handler] = [console]
    client_handlers: list[logging.Handler] = [console]
    log_dir_error: OSError | None = None

    try:
        directory = Path(settings.log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        root_handlers = [
            console,
            _file_handler(directory, "app.log", logging.INFO),
            _file_handler(directory, "error.log", logging.ERROR),
        ]
        access_handlers = [_file_handler(directory, "access.log", logging.INFO)]
        client_handlers = [_file_handler(directory, "client.log", logging.INFO)]
    except OSError as exc:
        log_dir_error = exc

    for handler in {*root_handlers, *access_handlers, *client_handlers}:
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)

    root = logging.getLogger()
    root.handlers[:] = root_handlers
    root.setLevel(settings.log_level.upper())

    for name, handlers in (("spotlight.access", access_handlers), ("spotlight.client", client_handlers)):
        logger = logging.getLogger(name)
        logger.handlers[:] = handlers
        logger.setLevel(logging.INFO)
        logger.propagate = False

    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True

    # These log full request details at INFO, which is noise at best.
    for name in ("httpx", "httpcore", "google_genai", "websockets"):
        logging.getLogger(name).setLevel(logging.WARNING)

    if log_dir_error is not None:
        logging.getLogger("spotlight.logging").warning(
            "LOG_DIR is not writable, logging to stdout only (%s)", type(log_dir_error).__name__
        )
