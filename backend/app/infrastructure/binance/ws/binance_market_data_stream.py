"""Implements `IMarketDataStream` against Binance's public Spot WebSocket API.

Each `subscribe_*` call opens its own dedicated single-stream connection
(`wss://.../ws/<streamName>`) rather than multiplexing everything onto one
shared "combined stream" connection — simpler to reason about, and one
symbol's connection dropping and reconnecting can't disturb any other
subscription.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import TypeVar

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.ports.market_data_stream import IMarketDataStream
from app.infrastructure.binance import mappers
from app.infrastructure.binance.ws.reconnecting_websocket import (
    ReconnectingWebSocket,
    ReconnectPolicy,
    WebSocketConnector,
    websockets_connector,
)

T = TypeVar("T")


class BinanceMarketDataStream(IMarketDataStream):
    def __init__(
        self,
        ws_base_url: str,
        *,
        connector: WebSocketConnector = websockets_connector,
        reconnect_policy: ReconnectPolicy = ReconnectPolicy(),
    ) -> None:
        self._ws_base_url = ws_base_url.rstrip("/")
        self._connector = connector
        self._reconnect_policy = reconnect_policy
        self._open_sockets: list[ReconnectingWebSocket] = []

    def subscribe_ticker(self, symbol: str) -> AsyncIterator[Ticker]:
        return self._stream(f"{symbol.lower()}@ticker", _parse_ticker_event)

    def subscribe_order_book(self, symbol: str) -> AsyncIterator[OrderBookSnapshot]:
        # Top-20 partial-depth snapshots, pushed every 100ms — far simpler
        # (and sufficient for display/decisioning) than consuming the raw
        # diff-depth stream, which requires maintaining a locally
        # synchronized order book per Binance's own reconciliation protocol.
        return self._stream(
            f"{symbol.lower()}@depth20@100ms", lambda data: _parse_order_book_event(symbol, data)
        )

    def subscribe_candles(self, symbol: str, interval: KlineInterval) -> AsyncIterator[Candle]:
        return self._stream(
            f"{symbol.lower()}@kline_{interval.value}",
            lambda data: _parse_kline_event(symbol, interval, data),
        )

    def subscribe_trades(self, symbol: str) -> AsyncIterator[Trade]:
        return self._stream(f"{symbol.lower()}@trade", lambda data: _parse_trade_event(symbol, data))

    async def _stream(self, stream_name: str, parse: Callable[[dict], T]) -> AsyncIterator[T]:
        url = f"{self._ws_base_url}/ws/{stream_name}"
        socket = ReconnectingWebSocket(
            lambda: url, connector=self._connector, reconnect_policy=self._reconnect_policy
        )
        self._open_sockets.append(socket)
        try:
            async for raw_message in socket.messages():
                yield parse(json.loads(raw_message))
        finally:
            await socket.close()
            if socket in self._open_sockets:
                self._open_sockets.remove(socket)

    async def close(self) -> None:
        for socket in list(self._open_sockets):
            await socket.close()
        self._open_sockets.clear()


def _parse_ticker_event(data: dict) -> Ticker:
    """24hr ticker stream payload — short keys, same values as `GET /ticker/24hr`."""
    return Ticker(
        symbol=data["s"],
        last_price=mappers.parse_decimal(data["c"]),
        bid_price=mappers.parse_decimal(data["b"]),
        ask_price=mappers.parse_decimal(data["a"]),
        high_price=mappers.parse_decimal(data["h"]),
        low_price=mappers.parse_decimal(data["l"]),
        volume=mappers.parse_decimal(data["v"]),
        quote_volume=mappers.parse_decimal(data["q"]),
        price_change_percent=mappers.parse_decimal(data["P"]),
        open_time=mappers.parse_timestamp_ms(data["O"]),
        close_time=mappers.parse_timestamp_ms(data["C"]),
    )


def _parse_order_book_event(symbol: str, data: dict) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol.upper(),
        last_update_id=int(data["lastUpdateId"]),
        bids=tuple(mappers.to_order_book_level(level) for level in data.get("bids", [])),
        asks=tuple(mappers.to_order_book_level(level) for level in data.get("asks", [])),
        retrieved_at=datetime.now(UTC),
    )


def _parse_kline_event(symbol: str, interval: KlineInterval, data: dict) -> Candle:
    kline = data["k"]
    return Candle(
        symbol=symbol.upper(),
        interval=interval,
        open_time=mappers.parse_timestamp_ms(kline["t"]),
        close_time=mappers.parse_timestamp_ms(kline["T"]),
        open=mappers.parse_decimal(kline["o"]),
        high=mappers.parse_decimal(kline["h"]),
        low=mappers.parse_decimal(kline["l"]),
        close=mappers.parse_decimal(kline["c"]),
        volume=mappers.parse_decimal(kline["v"]),
        quote_volume=mappers.parse_decimal(kline["q"]),
        trade_count=int(kline["n"]),
        is_closed=bool(kline["x"]),
    )


def _parse_trade_event(symbol: str, data: dict) -> Trade:
    price = mappers.parse_decimal(data["p"])
    quantity = mappers.parse_decimal(data["q"])
    return Trade(
        symbol=symbol.upper(),
        trade_id=int(data["t"]),
        price=price,
        quantity=quantity,
        quote_quantity=price * quantity,
        traded_at=mappers.parse_timestamp_ms(data["T"]),
        is_buyer_maker=bool(data["m"]),
    )
