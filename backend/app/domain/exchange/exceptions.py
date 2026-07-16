"""Exchange-agnostic exceptions.

Every Binance-specific error (HTTP status, `{"code": -1121, "msg": ...}`
body) is translated into one of these by
`infrastructure.binance.errors.map_binance_error` before it ever reaches a
caller — code depending on `ExchangeClient` never needs to know Binance
error codes exist. ``retryable`` drives the retry utility: a caller (or the
generic retry decorator) can check it instead of hard-coding which
exception types are safe to retry.
"""

from __future__ import annotations


class ExchangeError(Exception):
    """Base class for every exception raised by an exchange integration."""

    retryable = False

    def __init__(self, message: str, *, code: str | int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class ExchangeConnectionError(ExchangeError):
    """Network failure, timeout, or 5xx — the request may simply not have
    been processed at all, so it is safe to retry."""

    retryable = True


class ExchangeAuthenticationError(ExchangeError):
    """Bad/expired API key or signature. Never retryable — retrying with
    the same credentials will fail identically."""


class RateLimitExceededError(ExchangeError):
    """HTTP 429/418. Retryable, but the caller should honor
    ``retry_after_seconds`` rather than retrying immediately."""

    retryable = True

    def __init__(
        self,
        message: str,
        *,
        code: str | int | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message, code=code)
        self.retry_after_seconds = retry_after_seconds


class InvalidSymbolError(ExchangeError):
    """The requested symbol doesn't exist or isn't trading."""


class InsufficientBalanceError(ExchangeError):
    """An order was rejected because the account doesn't have enough of
    the required asset."""


class OrderRejectedError(ExchangeError):
    """An order was rejected for a reason other than balance (bad filter
    values, market closed, etc.)."""


class OrderNotFoundError(ExchangeError):
    """A lookup/cancel referenced an order id the exchange doesn't know."""


class ExchangeTimeoutError(ExchangeConnectionError):
    """The request timed out client-side before any response arrived."""
