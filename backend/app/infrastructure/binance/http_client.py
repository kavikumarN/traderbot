"""Low-level HTTP transport for Binance's REST API.

Every REST client (`rest/market_data_client.py`, `rest/account_client.py`,
`rest/order_client.py`) goes through this one class, so signing, rate
limiting, retry, and error mapping are each implemented exactly once.

The exact query string used for HMAC signing is sent byte-for-byte as the
request URL rather than handed to httpx's own `params=` encoder — letting
httpx re-encode a dict could reorder or re-escape it differently than what
was signed, which Binance would reject as an invalid signature.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx

from app.domain.exchange.exceptions import (
    ExchangeAuthenticationError,
    ExchangeConnectionError,
    ExchangeError,
    ExchangeTimeoutError,
)
from app.domain.exchange.ports.rate_limiter import RateLimiter
from app.infrastructure.binance.errors import map_binance_error
from app.infrastructure.binance.retry import RetryPolicy, retry_async
from app.infrastructure.binance.signing import build_query_string, sign_query_string

JsonValue = dict[str, Any] | list[Any]

DEFAULT_RATE_LIMITS: tuple[tuple[str, int], ...] = (("REQUEST_WEIGHT", 1),)


class BinanceHttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        api_secret: str | None,
        rate_limiter: RateLimiter,
        http_client: httpx.AsyncClient,
        recv_window_ms: int = 5000,
        retry_policy: RetryPolicy = RetryPolicy(),
        now_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._api_secret = api_secret
        self._rate_limiter = rate_limiter
        self._http = http_client
        self._recv_window_ms = recv_window_ms
        self._retry_policy = retry_policy
        self._now_ms = now_ms

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
        rate_limits: tuple[tuple[str, int], ...] = DEFAULT_RATE_LIMITS,
    ) -> JsonValue:
        return await self.request("GET", path, params, signed=signed, rate_limits=rate_limits)

    async def post(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = True,
        rate_limits: tuple[tuple[str, int], ...] = DEFAULT_RATE_LIMITS,
    ) -> JsonValue:
        return await self.request("POST", path, params, signed=signed, rate_limits=rate_limits)

    async def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = True,
        rate_limits: tuple[tuple[str, int], ...] = DEFAULT_RATE_LIMITS,
    ) -> JsonValue:
        return await self.request("DELETE", path, params, signed=signed, rate_limits=rate_limits)

    async def put(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool = False,
        rate_limits: tuple[tuple[str, int], ...] = DEFAULT_RATE_LIMITS,
    ) -> JsonValue:
        return await self.request("PUT", path, params, signed=signed, rate_limits=rate_limits)

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        signed: bool,
        rate_limits: tuple[tuple[str, int], ...] = DEFAULT_RATE_LIMITS,
    ) -> JsonValue:
        for bucket, weight in rate_limits:
            await self._rate_limiter.acquire(bucket, weight)

        async def _do() -> JsonValue:
            return await self._send_once(method, path, params or {}, signed=signed)

        return await retry_async(_do, policy=self._retry_policy)

    async def _send_once(self, method: str, path: str, params: dict[str, Any], *, signed: bool) -> JsonValue:
        request_params = dict(params)
        headers: dict[str, str] = {}
        if self._api_key:
            headers["X-MBX-APIKEY"] = self._api_key

        if signed:
            if not self._api_secret:
                raise ExchangeAuthenticationError(
                    "Binance API secret is not configured — cannot sign this request"
                )
            request_params["timestamp"] = self._now_ms()
            request_params["recvWindow"] = self._recv_window_ms

        query_string = build_query_string(request_params)

        if signed:
            # mypy/type-checkers can't see the None-check above narrowed this;
            # it's guarded by the `if not self._api_secret: raise` above.
            signature = sign_query_string(query_string, self._api_secret)  # type: ignore[arg-type]
            query_string = f"{query_string}&signature={signature}" if query_string else f"signature={signature}"

        url = f"{self._base_url}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        try:
            response = await self._http.request(method, url, headers=headers)
        except httpx.TimeoutException as exc:
            raise ExchangeTimeoutError(f"Request to {path} timed out: {exc}") from exc
        except httpx.TransportError as exc:
            raise ExchangeConnectionError(f"Request to {path} failed: {exc}") from exc

        if response.status_code >= 400:
            raise map_binance_error(
                response.status_code,
                _safe_json(response),
                retry_after_seconds=_parse_retry_after(response.headers),
            )

        try:
            return response.json()
        except ValueError as exc:
            raise ExchangeError(f"Binance returned a non-JSON response for {path}") from exc


def _safe_json(response: httpx.Response) -> dict[str, Any] | None:
    try:
        parsed = response.json()
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_retry_after(headers: httpx.Headers) -> float | None:
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
