from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.exchange.exceptions import ExchangeConnectionError, ExchangeError, OrderNotFoundError
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
async def test_place_order_verifies_before_resubmitting_on_connection_error() -> None:
    """A connection error on POST /order is ambiguous — the order may have
    landed. `place_order` must not immediately resend it; it should first
    check whether the order already exists under this client_order_id, and
    only resubmit once that check confirms it genuinely never landed."""
    http = FakeBinanceHttpClient(
        {"/api/v3/order": (ExchangeConnectionError("timed out"), OrderNotFoundError("no such order"), ORDER_RESPONSE)}
    )
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("50000"),
        client_order_id="abc",
    )

    order = await client.place_order(request)

    assert order.exchange_order_id == 1
    methods = [call["method"] for call in http.calls]
    assert methods == ["POST", "GET", "POST"]


@pytest.mark.asyncio
async def test_place_order_recovers_without_resubmitting_when_already_placed() -> None:
    """If the verify-by-client_order_id lookup finds the order, the original
    POST must have landed — placing it again would create a duplicate, so
    `place_order` should return the found order instead of resubmitting."""
    http = FakeBinanceHttpClient({"/api/v3/order": (ExchangeConnectionError("timed out"), ORDER_RESPONSE)})
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        quantity=Decimal("1"),
        price=Decimal("50000"),
        client_order_id="abc",
    )

    order = await client.place_order(request)

    assert order.exchange_order_id == 1
    methods = [call["method"] for call in http.calls]
    assert methods == ["POST", "GET"]


@pytest.mark.asyncio
async def test_place_order_without_client_order_id_raises_immediately_on_connection_error() -> None:
    """With no client_order_id there's nothing to verify by, so a connection
    error must surface immediately rather than attempting recovery."""
    http = FakeBinanceHttpClient({"/api/v3/order": (ExchangeConnectionError("timed out"),)})
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=Decimal("1"))

    with pytest.raises(ExchangeConnectionError):
        await client.place_order(request)

    assert [call["method"] for call in http.calls] == ["POST"]


@pytest.mark.asyncio
async def test_place_order_gives_up_after_max_attempts() -> None:
    http = FakeBinanceHttpClient(
        {
            "/api/v3/order": (
                ExchangeConnectionError("timed out"),
                OrderNotFoundError("no such order"),
                ExchangeConnectionError("timed out"),
                OrderNotFoundError("no such order"),
                ExchangeConnectionError("timed out"),
            )
        }
    )
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(
        symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=Decimal("1"), client_order_id="abc"
    )

    with pytest.raises(ExchangeConnectionError):
        await client.place_order(request)

    assert [call["method"] for call in http.calls] == ["POST", "GET", "POST", "GET", "POST"]


@pytest.mark.asyncio
async def test_place_order_propagates_non_connection_errors_without_recovery() -> None:
    http = FakeBinanceHttpClient({"/api/v3/order": (ExchangeError("rejected"),)})
    client = BinanceOrderClient(http)
    request = PlaceOrderRequest(
        symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=Decimal("1"), client_order_id="abc"
    )

    with pytest.raises(ExchangeError):
        await client.place_order(request)

    assert [call["method"] for call in http.calls] == ["POST"]


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
