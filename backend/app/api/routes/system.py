"""Health check and browser error reporting."""
import json
import logging
import re
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import AppSettings, CurrentUser, Provider
from app.core.config import APP_VERSION
from app.core.database import ping_database
from app.core.errors import ApiError
from app.core.rate_limit import client_log_limiter
from app.schemas.system import ClientLogRequest, HealthOut

router = APIRouter(tags=["system"])
client_logger = logging.getLogger("spotlight.client")

_MAX_MESSAGE_CHARS = 2000
_MAX_CONTEXT_CHARS = 2000
_SENSITIVE_KEY = re.compile(r"password|token|cookie|authorization|secret|api[_-]?key|transcript|audio", re.IGNORECASE)
_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}


def _sanitise_context(value: Any) -> Any:
    # A browser error report can capture app state, which must not leak secrets or speech into logs.
    if isinstance(value, dict):
        return {
            str(key): "***" if _SENSITIVE_KEY.search(str(key)) else _sanitise_context(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitise_context(item) for item in value]
    return value


@router.get("/ping", status_code=status.HTTP_204_NO_CONTENT)
def ping() -> None:
    """Say the server is up, for keep-alive pings and the host's health check.

    Deliberately touches nothing else: a ping every few minutes must not keep a serverless
    database awake, which /health would.
    """


@router.get("/health", response_model=HealthOut)
def health(response: Response, provider: Provider, settings: AppSettings) -> dict:
    """Report status. A failed database check returns 503, so the container healthcheck sees it."""
    database_ok = ping_database()
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if database_ok else "degraded",
        "version": APP_VERSION,
        "live_provider": settings.live_provider,
        "coach_available": provider.is_available(),
        "database": "ok" if database_ok else "error",
    }


@router.post("/client-logs", status_code=status.HTTP_204_NO_CONTENT)
def client_logs(body: ClientLogRequest, user: CurrentUser) -> None:
    """Write a browser error to client.log."""
    if not client_log_limiter.hit(user.id):
        raise ApiError(429, "too_many_requests", "Too many log messages.")
    context = ""
    if body.context:
        context = " context=" + json.dumps(_sanitise_context(body.context), default=str)[:_MAX_CONTEXT_CHARS]
    # %s keeps percent signs in browser text from being read as format codes.
    client_logger.log(_LEVELS[body.level], "%s%s", body.message[:_MAX_MESSAGE_CHARS], context)
