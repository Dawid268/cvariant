"""Domain errors and the single error response format used by every endpoint.

Every error - request validation, a broken business rule, an unknown route or an
unexpected crash - is returned as:

    {"error": {"code": "...", "message": "...", "details": [...]}}

so API clients handle exactly one shape.
"""

import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ---------- domain errors ----------


class DomainError(Exception):
    """Base class for business errors that map to a clean API response."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(DomainError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class BusinessRuleError(DomainError):
    """A request that is well-formed but breaks a business rule (e.g. dates out of order)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "business_rule_violation"


# ---------- response format ----------


class ErrorDetail(BaseModel):
    location: str = Field(description="Where the problem is: body, path, query or header")
    field: str | None = Field(description="Field as sent by the client, e.g. lastUsedYear")
    message: str
    type: str = Field(description="Machine-readable reason, e.g. missing or less_than_equal")


class ErrorBody(BaseModel):
    code: str = Field(description="Machine-readable error code, e.g. validation_error")
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def _validation_detail(error: Mapping[str, Any]) -> ErrorDetail:
    # loc is e.g. ("body", "lastUsedYear"), ("body", "skillIds", 1) or ("path", "skill_id").
    # The input value is deliberately not echoed back - it may contain personal data.
    location, *path = (str(part) for part in error["loc"])
    field = ".".join(path) or None
    if error["type"] == "json_invalid":
        field = None  # the position in a malformed JSON document is not a field
    return ErrorDetail(
        location=location,
        field=field,
        message=str(error["msg"]).removeprefix("Value error, "),
        type=str(error["type"]),
    )


# ---------- handlers ----------


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)  # noqa: S101 - registered only for DomainError
    return _error_response(exc.status_code, exc.code, exc.message)


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101 - registered only for it
    details = [_validation_detail(error) for error in exc.errors()]
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed",
        details,
    )


async def http_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Errors raised by the framework itself, e.g. an unknown route (404) or method (405)."""
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101 - registered only for it
    try:
        phrase = HTTPStatus(exc.status_code).phrase
    except ValueError:  # a non-standard status code, e.g. 499
        phrase = "HTTP Error"
    code = phrase.lower().replace(" ", "_").replace("-", "_")
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else phrase
    return _error_response(exc.status_code, code, message, headers=exc.headers)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort: log everything, tell the client nothing about the internals."""
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "internal_error",
        "Internal server error",
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)


# ---------- OpenAPI documentation ----------


def error_response_docs(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` entries so OpenAPI shows ErrorResponse instead of FastAPI's default."""
    descriptions = {
        status.HTTP_404_NOT_FOUND: "Resource not found",
        status.HTTP_409_CONFLICT: "Conflicts with existing data",
        status.HTTP_422_UNPROCESSABLE_CONTENT: "Invalid request or broken business rule",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "Unexpected server error",
    }
    return {
        code: {"model": ErrorResponse, "description": descriptions[code]} for code in status_codes
    }
