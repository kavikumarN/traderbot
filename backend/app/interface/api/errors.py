"""Maps domain/application exceptions to HTTP problem+json responses.

Every handler returns the same envelope (``ProblemDetail``) so API
consumers parse errors uniformly regardless of which layer raised them.
Unexpected exceptions are logged with a full traceback and returned as an
opaque 500 — internals never leak into the response body.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger, request_id_ctx
from app.domain.exceptions import (
    DomainError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    PermissionDeniedError,
    TokenRevokedError,
    ValidationError,
)
from app.domain.risk.exceptions import (
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
    RiskLimitExceededError,
)
from app.domain.strategy.exceptions import InvalidStrategyConfigError, UnknownStrategyTypeError
from app.domain.trading.exceptions import (
    AccountNotActiveError,
    InsufficientBalanceError,
    OrderNotCancelableError,
    OrderRejectedError,
)

logger = get_logger(__name__)

_STATUS_BY_EXCEPTION: dict[type[DomainError], int] = {
    EntityNotFoundError: status.HTTP_404_NOT_FOUND,
    EntityAlreadyExistsError: status.HTTP_409_CONFLICT,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidCredentialsError: status.HTTP_401_UNAUTHORIZED,
    InactiveUserError: status.HTTP_403_FORBIDDEN,
    InvalidTokenError: status.HTTP_401_UNAUTHORIZED,
    TokenRevokedError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    AccountNotActiveError: status.HTTP_403_FORBIDDEN,
    OrderRejectedError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InsufficientBalanceError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    OrderNotCancelableError: status.HTTP_409_CONFLICT,
    UnknownStrategyTypeError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidStrategyConfigError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    RiskLimitExceededError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    CircuitBreakerTrippedError: status.HTTP_409_CONFLICT,
    EmergencyStopActiveError: status.HTTP_409_CONFLICT,
}


def _problem(status_code: int, error_type: str, title: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": error_type,
            "title": title,
            "status": status_code,
            "detail": detail,
            "trace_id": request_id_ctx.get(),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        status_code = _STATUS_BY_EXCEPTION.get(type(exc), status.HTTP_400_BAD_REQUEST)
        return _problem(
            status_code=status_code,
            error_type=type(exc).__name__,
            title=type(exc).__name__.replace("Error", ""),
            detail=exc.message,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="RequestValidationError",
            title="Invalid request",
            detail="; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
        return _problem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="InternalServerError",
            title="Internal Server Error",
            detail="An unexpected error occurred. Reference the trace id when reporting this.",
        )
