from __future__ import annotations

import pytest

from app.domain.exchange.enums import KlineInterval
from app.infrastructure.binance.rest.market_data_client import BinanceMarketDataClient
from tests.fakes.fake_binance_http_client import FakeBinanceHttpClient


@pytest.mark.asyncio
async def test_get_exchange_info_maps_response() -> None:
    http = FakeBinanceHttpClient({"/api/v3/exchangeInfo": {"serverTime": 1735689600000, "symbols": []}})
    client = BinanceMarketDataClient(http)

    info = await client.get_exchange_info()

    assert info.symbols == ()
    assert http.calls[0]["signed"] is False


@pytest.mark.asyncio
async def test_get_ticker_uppercases_symbol_and_maps_response() -> None:
    http = FakeBinanceHttpClient(
        {
            "/api/v3/ticker/24hr": {
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
        }
    )
    client = BinanceMarketDataClient(http)

    ticker = await client.get_ticker("btcusdt")

    assert ticker.symbol == "BTCUSDT"
    assert http.calls[0]["params"] == {"symbol": "BTCUSDT"}


@pytest.mark.asyncio
async def test_get_order_book_passes_limit_through() -> None:
    http = FakeBinanceHttpClient({"/api/v3/depth": {"lastUpdateId": 1, "bids": [], "asks": []}})
    client = BinanceMarketDataClient(http)

    await client.get_order_book("BTCUSDT", limit=500)

    assert http.calls[0]["params"] == {"symbol": "BTCUSDT", "limit": 500}


@pytest.mark.asyncio
async def test_get_candles_builds_time_range_params() -> None:
    from datetime import UTC, datetime

    http = FakeBinanceHttpClient({"/api/v3/klines": []})
    client = BinanceMarketDataClient(http)

    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 1, 2, tzinfo=UTC)
    await client.get_candles("BTCUSDT", KlineInterval.ONE_HOUR, start_time=start, end_time=end)

    params = http.calls[0]["params"]
    assert params["interval"] == "1h"
    assert params["startTime"] == int(start.timestamp() * 1000)
    assert params["endTime"] == int(end.timestamp() * 1000)


@pytest.mark.asyncio
async def test_get_recent_trades_maps_each_entry() -> None:
    http = FakeBinanceHttpClient(
        {
            "/api/v3/trades": [
                {"id": 1, "price": "1", "qty": "1", "quoteQty": "1", "time": 0, "isBuyerMaker": True},
                {"id": 2, "price": "2", "qty": "2", "quoteQty": "4", "time": 0, "isBuyerMaker": False},
            ]
        }
    )
    client = BinanceMarketDataClient(http)

    trades = await client.get_recent_trades("BTCUSDT")

    assert len(trades) == 2
    assert trades[1].trade_id == 2
