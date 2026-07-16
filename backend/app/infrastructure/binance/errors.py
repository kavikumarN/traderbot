"""Translates Binance's HTTP status + `{"code", "msg"}` error body into the
exchange-agnostic exceptions in `app.domain.exchange.exceptions` — the one
place in the codebase allowed to know these numbers mean anything.

Reference: https://binance-docs.github.io/apidocs/spot/en/#error-codes
"""

from __future__ import annotations

from app.domain.exchange.exceptions import (
    ExchangeAuthenticationError,
    ExchangeConnectionError,
    ExchangeError,
    InsufficientBalanceError,
    InvalidSymbolError,
    OrderNotFoundError,
    OrderRejectedError,
    RateLimitExceededError,
)

_AUTHENTICATION_CODES = {-1002, -1021, -1022, -2014, -2015}
_INVALID_SYMBOL_CODES = {-1121}
_ORDER_NOT_FOUND_CODES = {-2011, -2013}
_INSUFFICIENT_BALANCE_CODES = {-2010, -2018, -2019}
_TOO_MANY_REQUESTS_CODES = {-1003}


def map_binance_error(
    status_code: int,
    body: dict[str, object] | None,
    *,
    retry_after_seconds: float | None = None,
) -> ExchangeError:
    code = body.get("code") if body else None
    msg = str(body.get("msg")) if body and body.get("msg") else f"Binance request failed with HTTP {status_code}"

    if status_code in (429, 418) or code in _TOO_MANY_REQUESTS_CODES:
        return RateLimitExceededError(msg, code=code, retry_after_seconds=retry_after_seconds)
    if status_code == 401 or code in _AUTHENTICATION_CODES:
        return ExchangeAuthenticationError(msg, code=code)
    if code in _INVALID_SYMBOL_CODES:
        return InvalidSymbolError(msg, code=code)
    if code in _ORDER_NOT_FOUND_CODES:
        return OrderNotFoundError(msg, code=code)
    if code in _INSUFFICIENT_BALANCE_CODES or "insufficient" in msg.lower():
        return InsufficientBalanceError(msg, code=code)
    if isinstance(code, int) and code <= -2000:
        return OrderRejectedError(msg, code=code)
    if status_code >= 500:
        return ExchangeConnectionError(msg, code=code)
    return ExchangeError(msg, code=code)
