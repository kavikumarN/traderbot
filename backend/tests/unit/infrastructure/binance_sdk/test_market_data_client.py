from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.domain.exchange.enums import KlineInterval
from app.infrastructure.binance_sdk.market_data_client import BinanceSdkMarketDataClient


def _dict_response(payload: dict) -> MagicMock:
    """Mimics an `ApiResponse[...]` whose `.data()` returns a pydantic model
    with a `.to_dict()` — the SDK's shape for every object-typed endpoint
    (ticker24hr, depth, exchange_info)."""
    response = MagicMock()
    response.data.return_value = SimpleNamespace(to_dict=lambda: payload)
    return response


def _array_response(rows: list) -> MagicMock:
    """Mimics an `ApiResponse[...]` whose `.data()` returns a plain list —
    the SDK's shape for `klines` (array-of-arrays, no object schema)."""
    response = MagicMock()
    response.data.return_value = rows
    return response


def _row(payload: dict) -> SimpleNamespace:
    """A single typed row from a list-of-objects endpoint (e.g. `get_trades`)."""
    return SimpleNamespace(to_dict=lambda: payload)


@pytest.mark.asyncio
async def test_get_exchange_info_maps_response() -> None:
    rest_api = MagicMock()
    rest_api.exchange_info.return_value = _dict_response({"serverTime": 1735689600000, "symbols": []})
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    info = await client.get_exchange_info()

    assert info.symbols == ()
    rest_api.exchange_info.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_ticker_uppercases_symbol_and_maps_response() -> None:
    rest_api = MagicMock()
    rest_api.ticker24hr.return_value = _dict_response(
        {
            "symbol": "BTCUSDT",
            "lastPrice": "1",
            "bidPrice": "1",
            "askPrice": "1",
            "highPrice": "1",
            "lowPrice": "1",
            "volume": "1",
            "quoteVolume": "1",
            "priceChangePercent": "0",
            "openTime": 0,
            "closeTime": 0,
        }
    )
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    ticker = await client.get_ticker("btcusdt")

    assert ticker.symbol == "BTCUSDT"
    rest_api.ticker24hr.assert_called_once_with(symbol="BTCUSDT")


@pytest.mark.asyncio
async def test_get_order_book_passes_limit_through() -> None:
    rest_api = MagicMock()
    rest_api.depth.return_value = _dict_response({"lastUpdateId": 1, "bids": [], "asks": []})
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    await client.get_order_book("BTCUSDT", limit=500)

    rest_api.depth.assert_called_once_with(symbol="BTCUSDT", limit=500)


@pytest.mark.asyncio
async def test_get_candles_builds_time_range_and_interval() -> None:
    rest_api = MagicMock()
    rest_api.klines.return_value = _array_response([])
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 2, tzinfo=UTC)
    await client.get_candles("BTCUSDT", KlineInterval.ONE_HOUR, start_time=start, end_time=end)

    _, kwargs = rest_api.klines.call_args
    assert kwargs["symbol"] == "BTCUSDT"
    assert kwargs["interval"].value == "1h"
    assert kwargs["start_time"] == int(start.timestamp() * 1000)
    assert kwargs["end_time"] == int(end.timestamp() * 1000)


@pytest.mark.asyncio
async def test_get_candles_maps_raw_rows() -> None:
    rest_api = MagicMock()
    rest_api.klines.return_value = _array_response(
        [[0, "1", "2", "0.5", "1.5", "10", 60000, "10", 5, "5", "5", "0"]]
    )
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    candles = await client.get_candles("BTCUSDT", KlineInterval.ONE_HOUR)

    assert len(candles) == 1
    assert candles[0].symbol == "BTCUSDT"
    assert candles[0].interval == KlineInterval.ONE_HOUR


@pytest.mark.asyncio
async def test_get_recent_trades_maps_each_entry() -> None:
    rest_api = MagicMock()
    rest_api.get_trades.return_value = _array_response(
        [
            _row({"id": 1, "price": "1", "qty": "1", "quoteQty": "1", "time": 0, "isBuyerMaker": True}),
            _row({"id": 2, "price": "2", "qty": "2", "quoteQty": "4", "time": 0, "isBuyerMaker": False}),
        ]
    )
    client = BinanceSdkMarketDataClient(SimpleNamespace(rest_api=rest_api))

    trades = await client.get_recent_trades("BTCUSDT")

    assert len(trades) == 2
    assert trades[1].trade_id == 2
    rest_api.get_trades.assert_called_once_with(symbol="BTCUSDT", limit=500)
