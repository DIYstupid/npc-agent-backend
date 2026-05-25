import logging
from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for application errors returned through the API."""

    status_code = 500
    code = "internal_error"
    default_message = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message or self.default_message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class BusinessError(AppError):
    status_code = 400
    code = "business_error"
    default_message = "Business rule violation"


class ResourceNotFoundError(BusinessError):
    status_code = 404
    code = "resource_not_found"

    def __init__(
        self,
        resource: str,
        identifier: str | None = None,
        *,
        message: str | None = None,
        code: str | None = None,
    ) -> None:
        resolved_message = message or (
            f"{resource} not found: {identifier}" if identifier else f"{resource} not found"
        )
        details: dict[str, str] = {"resource": resource}
        if identifier is not None:
            details["identifier"] = identifier

        super().__init__(
            resolved_message,
            code=code or self.code,
            status_code=self.status_code,
            details=details,
        )


class NpcNotFoundError(ResourceNotFoundError):
    def __init__(self, npc_id: str) -> None:
        super().__init__("npc", npc_id, code="npc_not_found")


class PlayerNotFoundError(ResourceNotFoundError):
    def __init__(self, player_id: str) -> None:
        super().__init__("player", player_id, code="player_not_found")


class LongTermMemoryNotFoundError(ResourceNotFoundError):
    def __init__(self, memory_id: str) -> None:
        super().__init__(
            "long_term_memory",
            memory_id,
            message=f"Long-term memory not found: {memory_id}",
            code="long_term_memory_not_found",
        )


class PromptTraceNotFoundError(ResourceNotFoundError):
    def __init__(self, request_id: str | None = None) -> None:
        super().__init__(
            "prompt_trace",
            request_id,
            message=(
                f"Prompt trace not found: {request_id}"
                if request_id
                else "Prompt trace not found"
            ),
            code="prompt_trace_not_found",
        )


def error_response_body(
    *,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details is not None:
        error["details"] = details

    return {"error": error}


def _http_error_code(status_code: int) -> str:
    if status_code == 404:
        return "not_found"
    if status_code == 405:
        return "method_not_allowed"
    return "http_error"


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            error_response_body(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            )
        ),
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    details = None if isinstance(exc.detail, str) else exc.detail

    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content=jsonable_encoder(
            error_response_body(
                code=_http_error_code(exc.status_code),
                message=message,
                details=details,
            )
        ),
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            error_response_body(
                code="request_validation_error",
                message="Request validation failed",
                details=exc.errors(),
            )
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=error_response_body(
            code="internal_error",
            message="Internal server error",
        ),
    )


def register_exception_handlers(app) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
