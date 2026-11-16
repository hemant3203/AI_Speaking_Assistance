"""The FastAPI application."""
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.routes import analytics, auth, gamification, live, practice, system
from app.core.config import APP_VERSION, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, new_request_context
from app.services.admin import ensure_admin
from app.services.live.bridge import drain_background_tasks
from app.services.live.gemini import GeminiProvider
from app.services.live.mock import MockProvider
from app.services.live.provider import LiveProvider
from app.services.live.registry import LiveRegistry
from app.services.live.usage import abandon_stale_sessions

logger = logging.getLogger("spotlight.app")
access_logger = logging.getLogger("spotlight.access")


class AccessLogMiddleware:
    """Starts the request context and writes one access log line per request or WebSocket.

    Written as plain ASGI because Starlette's BaseHTTPMiddleware runs the app in a separate task, which
    would hide the request context from the handlers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self._app(scope, receive, send)
            return

        context = new_request_context()
        started = time.perf_counter()
        # For a WebSocket this ends up as the close code, which says far more than 101 would.
        status_code = 500 if scope["type"] == "http" else 1000

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", []).append((b"x-request-id", context.request_id.encode()))
            elif message["type"] == "websocket.close":
                status_code = message.get("code", 1000)
            await send(message)

        try:
            await self._app(scope, receive, capture_status)
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            access_logger.info(
                "%s %s %d %.0fms rid=%s uid=%s",
                scope.get("method", "WS"), scope["path"], status_code, elapsed_ms, context.request_id, context.user_id,
            )


def _build_provider(settings: Settings) -> LiveProvider:
    return MockProvider() if settings.live_provider == "mock" else GeminiProvider(settings)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    app.state.live_provider = _build_provider(settings)
    app.state.live_registry = LiveRegistry(settings.max_concurrent_live_sessions)
    abandoned = await run_in_threadpool(abandon_stale_sessions)
    await run_in_threadpool(ensure_admin, settings)
    logger.info(
        "started version=%s env=%s provider=%s abandoned_sessions=%d",
        APP_VERSION, settings.app_env, settings.live_provider, abandoned,
    )
    yield
    await drain_background_tasks()


def create_app() -> FastAPI:
    """Build the application. Reading settings here is what refuses a boot on a bad JWT_SECRET."""
    settings = get_settings()
    app = FastAPI(title="Spotlight API", version=APP_VERSION, lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AccessLogMiddleware)
    register_exception_handlers(app)
    for module in (auth, practice, live, gamification, analytics, system):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
