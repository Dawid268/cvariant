from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


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


async def domain_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)  # noqa: S101 - registered only for DomainError
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)
