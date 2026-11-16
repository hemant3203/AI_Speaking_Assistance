"""Request and response models for system endpoints."""
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    """Body of GET /health."""

    status: Literal["ok", "degraded"]
    version: str
    live_provider: str
    coach_available: bool
    database: Literal["ok", "error"]


class ClientLogRequest(BaseModel):
    """Body of POST /client-logs. Long text is truncated when written, not rejected: a stack trace is
    exactly what we want to receive, and failing the report would lose it."""

    level: Literal["debug", "info", "warn", "warning", "error"]
    message: str = Field(max_length=20000)
    context: dict[str, Any] | None = None
