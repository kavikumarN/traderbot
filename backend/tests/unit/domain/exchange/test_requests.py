from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exchange.enums import OrderSide, OrderType
from app.domain.exchange.models.requests import PlaceOrderRequest


def test_limit_order_requires_a_price() -> None:
    with pytest.raises(ValueError, match="require a price"):
        PlaceOrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.LIMIT, quantity=Decimal("1"))


def test_market_order_does_not_require_a_price() -> None:
    request = PlaceOrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=Decimal("1"))
    assert request.price is None


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_quantity_must_be_positive(quantity: Decimal) -> None:
    with pytest.raises(ValueError, match="positive"):
        PlaceOrderRequest(
            symbol="BTCUSDT", side=OrderSide.BUY, type=OrderType.MARKET, quantity=quantity
        )
