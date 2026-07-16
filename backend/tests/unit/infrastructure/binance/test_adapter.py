from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide, OrderType
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.infrastructure.binance.adapter import BinanceExchangeAdapter
from tests.fakes.fake_binance_http_client import FakeBinanceHttpClient

ORDER_RESPONSE = {
    "symbol": "BTCUSDT",
    "orderId": 1,
    "clientOrderId": "abc",
    "price": "0",
    "origQty": "1",
    "executedQty": "1",
    "cummulativeQuoteQty": "50000",
    "status": "FILLED",
    "timeInForce": "GTC",
    "type": "MARKET",
    "side": "BUY",
    "transactTime": 0,
}


def make_adapter(responses: dict) -> BinanceExchangeAdapter:
    http = FakeBinanceHttpClient(responses)
    return BinanceExchangeAdapter(http)


def test_adapter_satisfies_the_exchange_client_port() -> None:
    adapter = make_adapter({})
    assert isinstance(adapter, ExchangeClient)


@pytest.mark.asyncio
async def test_adapter_delegates_market_data_reads() -> None:
    adapter = make_adapter(
        {
            "/api/v3/exchangeInfo": {"serverTime": 0, "symbols": []},
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
            },
            "/api/v3/depth": {"lastUpdateId": 1, "bids": [], "asks": []},
            "/api/v3/klines": [],
            "/api/v3/trades": [],
        }
    )

    assert (await adapter.get_exchange_info()).symbols == ()
    assert (await adapter.get_ticker("BTCUSDT")).symbol == "BTCUSDT"
    assert (await adapter.get_order_book("BTCUSDT")).last_update_id == 1
    assert await adapter.get_candles("BTCUSDT", KlineInterval.ONE_HOUR) == []
    assert await adapter.get_recent_trades("BTCUSDT") == []


@pytest.mark.asyncio
async def test_adapter_delegates_account_reads() -> None:
    adapter = make_adapter({"/api/v3/account": {"balances": [{"asset": "BTC", "free": "1", "locked": "0"}]}})

    balances = await adapter.get_balances()

    assert balances[0].asset == "BTC"


@pytest.mark.asyncio
async def test_adapter_delegates_order_operations() -> None:
    adapter = make_adapter(
        {
            "/api/v3/order": ORDER_RESPONSE,
            "/api/v3/openOrders": [ORDER_RESPONSE],
        }
    )

    placed = await adapter.place_order(
        PlaceOrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=Decimal("1"))
    )
    fetched = await adapter.get_order("BTCUSDT", exchange_order_id=1)
    cancelled = await adapter.cancel_order("BTCUSDT", exchange_order_id=1)
    open_orders = await adapter.get_open_orders()

    assert placed.exchange_order_id == 1
    assert fetched.exchange_order_id == 1
    assert cancelled.exchange_order_id == 1
    assert len(open_orders) == 1


@pytest.mark.asyncio
async def test_adapter_exposes_the_narrow_clients_for_direct_use() -> None:
    adapter = make_adapter({"/api/v3/ticker/24hr": {
        "symbol": "BTCUSDT", "lastPrice": "1", "bidPrice": "1", "askPrice": "1",
        "highPrice": "1", "lowPrice": "1", "volume": "1", "quoteVolume": "1",
        "priceChangePercent": "0", "openTime": 0, "closeTime": 0,
    }})

    # A caller that only needs market data can depend on `adapter.market_data`
    # (an IMarketDataReader) instead of the full ExchangeClient.
    ticker = await adapter.market_data.get_ticker("BTCUSDT")
    assert ticker.symbol == "BTCUSDT"


@pytest.mark.asyncio
async def test_adapter_accepts_an_injected_market_data_reader() -> None:
    """A caller (e.g. `deps.get_exchange_client`) may swap in a different
    `IMarketDataReader` implementation — such as `BinanceSdkMarketDataClient`,
    backed by Binance's official connector — without touching account reads
    or order placement, which always go through `http`."""
    http = FakeBinanceHttpClient({"/api/v3/account": {"balances": []}})

    class StubMarketDataReader:
        async def get_ticker(self, symbol: str):
            return "stubbed"

    adapter = BinanceExchangeAdapter(http, market_data=StubMarketDataReader())

    assert await adapter.market_data.get_ticker("BTCUSDT") == "stubbed"
    assert await adapter.get_balances() == []
