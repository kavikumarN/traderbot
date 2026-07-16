"""Implements `IMarketDataReader` against Binance's public Spot REST API.

No authentication needed for any endpoint here — Binance serves market
data to anyone.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.infrastructure.binance import mappers
from app.infrastructure.binance.http_client import BinanceHttpClient


class BinanceMarketDataClient(IMarketDataReader):
    def __init__(self, http: BinanceHttpClient) -> None:
        self._http = http

    async def get_exchange_info(self) -> ExchangeInfo:
        data = await self._http.get("/api/v3/exchangeInfo", rate_limits=(("REQUEST_WEIGHT", 20),))
        return mappers.to_exchange_info(data)

    async def get_ticker(self, symbol: str) -> Ticker:
        data = await self._http.get(
            "/api/v3/ticker/24hr", {"symbol": symbol.upper()}, rate_limits=(("REQUEST_WEIGHT", 2),)
        )
        return mappers.to_ticker(data)

    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        data = await self._http.get(
            "/api/v3/depth",
            {"symbol": symbol.upper(), "limit": limit},
            rate_limits=(("REQUEST_WEIGHT", _order_book_weight(limit)),),
        )
        return mappers.to_order_book(symbol.upper(), data)

    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        params: dict[str, object] = {"symbol": symbol.upper(), "interval": interval.value, "limit": limit}
        if start_time is not None:
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time is not None:
            params["endTime"] = int(end_time.timestamp() * 1000)

        data = await self._http.get("/api/v3/klines", params, rate_limits=(("REQUEST_WEIGHT", 2),))
        return [mappers.to_candle(symbol.upper(), interval, row) for row in data]

    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]:
        data = await self._http.get(
            "/api/v3/trades", {"symbol": symbol.upper(), "limit": limit}, rate_limits=(("REQUEST_WEIGHT", 10),)
        )
        return [mappers.to_trade(symbol.upper(), row) for row in data]


def _order_book_weight(limit: int) -> int:
    """Approximates Binance's tiered weight for GET /depth by `limit`."""
    if limit <= 100:
        return 5
    if limit <= 500:
        return 25
    if limit <= 1000:
        return 50
    return 250
