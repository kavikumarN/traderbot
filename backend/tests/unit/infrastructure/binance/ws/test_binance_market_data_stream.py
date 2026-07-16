from __future__ import annotations

import json

import pytest

from app.domain.exchange.enums import KlineInterval
from app.infrastructure.binance.ws.binance_market_data_stream import BinanceMarketDataStream
from tests.fakes.fake_websocket import FakeConnector, FakeWebSocketConnection


def make_stream(message: dict) -> tuple[BinanceMarketDataStream, FakeConnector]:
    connection = FakeWebSocketConnection([json.dumps(message)])
    connector = FakeConnector([connection])
    stream = BinanceMarketDataStream("wss://stream.binance.com:9443", connector=connector)
    return stream, connector


@pytest.mark.asyncio
async def test_subscribe_ticker_parses_short_key_payload() -> None:
    stream, connector = make_stream(
        {
            "s": "BTCUSDT",
            "c": "62483.13",
            "b": "62483.13",
            "a": "62483.14",
            "h": "63000",
            "l": "62000",
            "v": "1000",
            "q": "62000000",
            "P": "-1.2",
            "O": 1735689600000,
            "C": 1735776000000,
        }
    )

    async for ticker in stream.subscribe_ticker("btcusdt"):
        assert ticker.symbol == "BTCUSDT"
        assert str(ticker.last_price) == "62483.13"
        break

    assert connector.urls == ["wss://stream.binance.com:9443/ws/btcusdt@ticker"]
    await stream.close()


@pytest.mark.asyncio
async def test_subscribe_order_book_parses_partial_depth_payload() -> None:
    stream, connector = make_stream({"lastUpdateId": 42, "bids": [["100", "1"]], "asks": [["101", "2"]]})

    async for book in stream.subscribe_order_book("btcusdt"):
        assert book.symbol == "BTCUSDT"
        assert book.last_update_id == 42
        assert book.best_bid.price == 100
        break

    assert connector.urls == ["wss://stream.binance.com:9443/ws/btcusdt@depth20@100ms"]
    await stream.close()


@pytest.mark.asyncio
async def test_subscribe_candles_parses_kline_event() -> None:
    stream, connector = make_stream(
        {
            "k": {
                "t": 1735689600000,
                "T": 1735689659999,
                "o": "1",
                "h": "2",
                "l": "0.5",
                "c": "1.5",
                "v": "100",
                "q": "150",
                "n": 42,
                "x": False,
            }
        }
    )

    async for candle in stream.subscribe_candles("btcusdt", KlineInterval.ONE_MINUTE):
        assert candle.symbol == "BTCUSDT"
        assert candle.is_closed is False
        assert candle.trade_count == 42
        break

    assert connector.urls == ["wss://stream.binance.com:9443/ws/btcusdt@kline_1m"]
    await stream.close()


@pytest.mark.asyncio
async def test_subscribe_trades_computes_quote_quantity() -> None:
    stream, connector = make_stream({"t": 1, "p": "100", "q": "2", "T": 1735689600000, "m": True})

    async for trade in stream.subscribe_trades("btcusdt"):
        assert trade.quote_quantity == 200
        assert trade.is_buyer_maker is True
        break

    assert connector.urls == ["wss://stream.binance.com:9443/ws/btcusdt@trade"]
    await stream.close()


@pytest.mark.asyncio
async def test_close_closes_every_open_subscription() -> None:
    connection_a = FakeWebSocketConnection([json.dumps({"t": 1, "p": "1", "q": "1", "T": 0, "m": False})])
    connection_b = FakeWebSocketConnection([json.dumps({"t": 2, "p": "1", "q": "1", "T": 0, "m": False})])
    connector = FakeConnector([connection_a, connection_b])
    stream = BinanceMarketDataStream("wss://stream.binance.com:9443", connector=connector)

    async for _trade in stream.subscribe_trades("btcusdt"):
        break
    async for _trade in stream.subscribe_trades("ethusdt"):
        break

    await stream.close()

    assert connection_a.closed is True
    assert connection_b.closed is True
