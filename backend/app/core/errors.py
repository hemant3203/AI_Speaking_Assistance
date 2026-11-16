"""The uniform `{detail, code}` error body required by section 3 of the contract."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("spotlight.errors")

_DEFAULT_CODES = {
    400: "bad_request",
    401: "not_authenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    429: "too_many_requests",
}


class ApiError(Exception):
    """An expected failure that maps directly to an HTTP response."""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def not_found(detail: str = "Not found.", code: str = "not_found") -> ApiError:
    """Build a 404. Also used for other users' resources, so existence is never revealed."""
    return ApiError(404, code, detail)


def _body(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


def _first_validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid request."
    first = errors[0]
    location = ".".join(str(part) for part in first.get("loc", ()) if part not in ("body", "query", "path"))
    message = str(first.get("msg", "Invalid value.")).removeprefix("Value error, ")
    return f"{location}: {message}" if location else message


def register_exception_handlers(app: FastAPI) -> None:
    """Route every failure through the uniform error body."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(_body(exc.detail, exc.code), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(_body(_first_validation_message(exc), "validation_error"), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _DEFAULT_CODES.get(exc.status_code, "http_error")
        return JSONResponse(_body(str(exc.detail), code), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(_body("Something went wrong on our side.", "internal_error"), status_code=500)
