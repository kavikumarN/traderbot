from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.infrastructure.binance.rest.order_client import BinanceOrderClient
from tests.fakes.fake_binance_http_client import FakeBinanceHttpClient

ORDER_RESPONSE = {
    "symbol": "BTCUSDT",
    "orderId": 1,
    "clientOrderId": "abc",
    "price": "50000",
    "origQty": "1",
    "executedQty": "0",
    "cummulativeQuoteQty": "0",
    "status": "NEW",
    "timeInForce": "GTC",
    "type": "LIMIT",
    "side": "BUY",
    "transactTime": 1735689600000,
}


@pytest.mark.asyncio
async def test_place_order_sends_all_fields_and_signs() -> None:
    http = FakeBinanceHttpClient({"/api/v3/order": ORDER_RESPONSE})
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(
        symbol="btcusdt",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("50000"),
        time_in_force=TimeInForce.GTC,
        client_order_id="my-id",
    )

    order = await client.place_order(request)

    assert order.exchange_order_id == 1
    call = http.calls[0]
    assert call["signed"] is True
    assert call["params"]["symbol"] == "BTCUSDT"
    assert call["params"]["price"] == "50000"
    assert call["params"]["timeInForce"] == "GTC"
    assert call["params"]["newClientOrderId"] == "my-id"


@pytest.mark.asyncio
async def test_place_market_order_omits_price_and_time_in_force() -> None:
    http = FakeBinanceHttpClient({"/api/v3/order": {**ORDER_RESPONSE, "type": "MARKET", "timeInForce": None}})
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(symbol="BTCUSDT", side=OrderSide.SELL, type=OrderType.MARKET, quantity=Decimal("1"))

    await client.place_order(request)

    params = http.calls[0]["params"]
    assert "price" not in params
    assert "timeInForce" not in params


@pytest.mark.asyncio
async def test_cancel_order_by_exchange_id() -> None:
    http = FakeBinanceHttpClient({"/api/v3/order": {**ORDER_RESPONSE, "status": "CANCELED"}})
    client = BinanceOrderClient(http)

    order = await client.cancel_order("BTCUSDT", exchange_order_id=1)

    assert order.status.value == "CANCELED"
    assert http.calls[0]["params"] == {"symbol": "BTCUSDT", "orderId": 1}


@pytest.mark.asyncio
async def test_cancel_order_by_client_order_id() -> None:
    http = FakeBinanceHttpClient({"/api/v3/order": ORDER_RESPONSE})
    client = BinanceOrderClient(http)

    await client.cancel_order("BTCUSDT", client_order_id="my-id")

    assert http.calls[0]["params"] == {"symbol": "BTCUSDT", "origClientOrderId": "my-id"}


@pytest.mark.asyncio
async def test_cancel_order_requires_one_reference() -> None:
    http = FakeBinanceHttpClient({})
    client = BinanceOrderClient(http)

    with pytest.raises(ValueError, match="Provide either"):
        await client.cancel_order("BTCUSDT")


@pytest.mark.asyncio
async def test_get_open_orders_charges_more_weight_when_symbol_omitted() -> None:
    http = FakeBinanceHttpClient({"/api/v3/openOrders": [ORDER_RESPONSE]})
    client = BinanceOrderClient(http)

    orders = await client.get_open_orders()

    assert len(orders) == 1
    assert http.calls[0]["params"] == {}


@pytest.mark.asyncio
async def test_get_open_orders_filters_by_symbol() -> None:
    http = FakeBinanceHttpClient({"/api/v3/openOrders": [ORDER_RESPONSE]})
    client = BinanceOrderClient(http)

    await client.get_open_orders("BTCUSDT")

    assert http.calls[0]["params"] == {"symbol": "BTCUSDT"}
