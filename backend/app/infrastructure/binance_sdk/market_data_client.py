"""Implements `IMarketDataReader` using Binance's official `binance-sdk-spot`
connector (https://developers.binance.com/en/docs/sdks-tools/connectors/python)
instead of the hand-rolled `httpx` client in
`infrastructure/binance/rest/market_data_client.py`.

The SDK's REST client is synchronous (built on `requests`), so every call
here is offloaded to a worker thread via `asyncio.to_thread` — the only
blocking I/O boundary in an otherwise fully async backend.

Response objects are converted back to Binance's raw camelCase JSON via
`.to_dict()` and fed through the existing `infrastructure.binance.mappers`
functions, so the anti-corruption layer (and its quirks knowledge) stays in
exactly one place regardless of which HTTP client fetched the data.

Order placement and account reads intentionally keep using the hand-rolled,
HMAC-signed `BinanceHttpClient` (see `infrastructure/binance/adapter.py`) —
this SDK-backed client only ever touches Binance's public, unauthenticated
market-data endpoints.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from binance_sdk_spot.rest_api.models.enums import KlinesIntervalEnum
from binance_sdk_spot.spot import Spot

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.infrastructure.binance import mappers


class BinanceSdkMarketDataClient(IMarketDataReader):
    def __init__(self, client: Spot) -> None:
        self._client = client

    async def get_exchange_info(self) -> ExchangeInfo:
        response = await asyncio.to_thread(self._client.rest_api.exchange_info)
        return mappers.to_exchange_info(response.data().to_dict())

    async def get_ticker(self, symbol: str) -> Ticker:
        response = await asyncio.to_thread(self._client.rest_api.ticker24hr, symbol=symbol.upper())
        return mappers.to_ticker(response.data().to_dict())

    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        response = await asyncio.to_thread(self._client.rest_api.depth, symbol=symbol.upper(), limit=limit)
        return mappers.to_order_book(symbol.upper(), response.data().to_dict())

    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        response = await asyncio.to_thread(
            self._client.rest_api.klines,
            symbol=symbol.upper(),
            interval=KlinesIntervalEnum(interval.value),
            limit=limit,
            start_time=int(start_time.timestamp() * 1000) if start_time is not None else None,
            end_time=int(end_time.timestamp() * 1000) if end_time is not None else None,
        )
        return [mappers.to_candle(symbol.upper(), interval, row) for row in response.data()]

    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]:
        response = await asyncio.to_thread(self._client.rest_api.get_trades, symbol=symbol.upper(), limit=limit)
        return [mappers.to_trade(symbol.upper(), row.to_dict()) for row in response.data()]
