from __future__ import annotations

import pytest

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
from app.infrastructure.binance.errors import map_binance_error


@pytest.mark.parametrize("status_code", [429, 418])
def test_too_many_requests_status_maps_to_rate_limit_error(status_code: int) -> None:
    error = map_binance_error(status_code, {"code": -1003, "msg": "Too many requests"}, retry_after_seconds=5.0)
    assert isinstance(error, RateLimitExceededError)
    assert error.retry_after_seconds == 5.0
    assert error.retryable is True


def test_401_maps_to_authentication_error() -> None:
    error = map_binance_error(401, {"code": -2015, "msg": "Invalid API-key"})
    assert isinstance(error, ExchangeAuthenticationError)
    assert error.retryable is False


def test_bad_symbol_code_maps_to_invalid_symbol_error() -> None:
    error = map_binance_error(400, {"code": -1121, "msg": "Invalid symbol."})
    assert isinstance(error, InvalidSymbolError)


def test_no_such_order_maps_to_order_not_found() -> None:
    error = map_binance_error(400, {"code": -2013, "msg": "Order does not exist."})
    assert isinstance(error, OrderNotFoundError)


def test_insufficient_balance_code_maps_correctly() -> None:
    error = map_binance_error(400, {"code": -2010, "msg": "Account has insufficient balance."})
    assert isinstance(error, InsufficientBalanceError)


def test_insufficient_balance_detected_from_message_even_with_unknown_code() -> None:
    error = map_binance_error(400, {"code": -9999, "msg": "insufficient funds for this order"})
    assert isinstance(error, InsufficientBalanceError)


def test_generic_order_rejection_for_other_minus_2000_codes() -> None:
    error = map_binance_error(400, {"code": -2011, "msg": "Unknown order sent."})
    # -2011 is actually mapped as order-not-found here; use a code with no
    # specific mapping to exercise the generic -2000 fallback.
    error2 = map_binance_error(400, {"code": -2099, "msg": "Some other order-related rejection"})
    assert isinstance(error, OrderNotFoundError)
    assert isinstance(error2, OrderRejectedError)


def test_5xx_maps_to_connection_error() -> None:
    error = map_binance_error(503, None)
    assert isinstance(error, ExchangeConnectionError)
    assert error.retryable is True


def test_unmapped_4xx_falls_back_to_generic_exchange_error() -> None:
    error = map_binance_error(400, {"code": -1100, "msg": "Illegal characters found in a parameter."})
    assert type(error) is ExchangeError
    assert error.retryable is False


def test_missing_body_still_produces_a_usable_message() -> None:
    error = map_binance_error(500, None)
    assert "HTTP 500" in error.message
