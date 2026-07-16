from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.domain.exchange.exceptions import (
    ExchangeAuthenticationError,
    ExchangeConnectionError,
    InvalidSymbolError,
    RateLimitExceededError,
)
from app.infrastructure.binance.http_client import BinanceHttpClient
from app.infrastructure.binance.rate_limiter import InMemoryTokenBucketRateLimiter
from app.infrastructure.binance.retry import RetryPolicy
from app.infrastructure.binance.signing import sign_query_string


def make_client(handler, **overrides) -> BinanceHttpClient:
    transport = httpx.MockTransport(handler)
    httpx_client = httpx.AsyncClient(transport=transport)
    limiter = InMemoryTokenBucketRateLimiter({})  # unlimited, so tests run instantly
    defaults = dict(
        base_url="https://api.binance.com",
        api_key="test-api-key",
        api_secret="test-api-secret",
        rate_limiter=limiter,
        http_client=httpx_client,
        recv_window_ms=5000,
        retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0.001),
        now_ms=lambda: 1735689600000,
    )
    defaults.update(overrides)
    return BinanceHttpClient(**defaults)


@pytest.mark.asyncio
async def test_unsigned_get_sends_no_signature_or_api_key_requirement() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, api_key=None, api_secret=None)
    result = await client.get("/api/v3/ticker/24hr", {"symbol": "BTCUSDT"})

    assert result == {"ok": True}
    assert "signature" not in captured["url"]
    assert "X-Mbx-Apikey" not in captured["headers"] and "x-mbx-apikey" not in captured["headers"]


@pytest.mark.asyncio
async def test_signed_request_includes_api_key_header_and_valid_signature() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["query"] = parse_qs(urlparse(str(request.url)).query)
        return httpx.Response(200, json={"balances": []})

    client = make_client(handler)
    await client.get("/api/v3/account", signed=True)

    assert captured["headers"]["x-mbx-apikey"] == "test-api-key"
    query = captured["query"]
    assert query["timestamp"] == ["1735689600000"]
    assert query["recvWindow"] == ["5000"]

    # The signature must match a recomputation over the *same* query string
    # (excluding the signature itself) — proves the exact bytes sent match
    # what was signed, not some re-encoded variant.
    unsigned_query = "timestamp=1735689600000&recvWindow=5000"
    expected_signature = sign_query_string(unsigned_query, "test-api-secret")
    assert query["signature"] == [expected_signature]


@pytest.mark.asyncio
async def test_signed_request_without_api_secret_raises_authentication_error() -> None:
    client = make_client(lambda request: httpx.Response(200, json={}), api_secret=None)
    with pytest.raises(ExchangeAuthenticationError):
        await client.get("/api/v3/account", signed=True)


@pytest.mark.asyncio
async def test_error_response_is_mapped_to_a_domain_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})

    client = make_client(handler)
    with pytest.raises(InvalidSymbolError):
        await client.get("/api/v3/ticker/24hr", {"symbol": "NOPE"})


@pytest.mark.asyncio
async def test_429_maps_to_rate_limit_error_with_retry_after() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"code": -1003, "msg": "Too many requests"}, headers={"Retry-After": "3"})

    client = make_client(handler, retry_policy=RetryPolicy(max_attempts=1))
    with pytest.raises(RateLimitExceededError) as exc_info:
        await client.get("/api/v3/ticker/24hr")
    assert exc_info.value.retry_after_seconds == 3.0


@pytest.mark.asyncio
async def test_transport_error_is_retried_then_raises_connection_error() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        raise httpx.ConnectError("boom")

    client = make_client(handler, retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001))
    with pytest.raises(ExchangeConnectionError):
        await client.get("/api/v3/ticker/24hr")

    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_transient_failure_then_success_is_retried_transparently() -> None:
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(503, json={"msg": "server hiccup"})
        return httpx.Response(200, json={"ok": True})

    client = make_client(handler, retry_policy=RetryPolicy(max_attempts=3, base_delay_seconds=0.001))
    result = await client.get("/api/v3/ticker/24hr")

    assert result == {"ok": True}
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_post_order_places_params_in_the_url_not_a_body() -> None:
    """Guards the design decision in http_client.py: everything goes in the
    query string (even for POST) so the signed bytes are unambiguous."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = str(request.url.query)
        captured["body"] = request.content
        return httpx.Response(200, json={"orderId": 1})

    client = make_client(handler)
    await client.post("/api/v3/order", {"symbol": "BTCUSDT", "side": "BUY"}, signed=True)

    assert b"symbol=BTCUSDT" in captured["query"]
    assert captured["body"] == b""
