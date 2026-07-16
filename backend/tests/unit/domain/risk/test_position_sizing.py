from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exceptions import ValidationError
from app.domain.exchange.enums import OrderSide
from app.domain.risk.position_sizing import (
    calculate_position_size,
    calculate_stop_loss_price,
    calculate_take_profit_price,
)


def test_stop_loss_price_below_entry_for_long() -> None:
    price = calculate_stop_loss_price(entry_price=Decimal("100"), side=OrderSide.BUY, stop_loss_pct=Decimal("0.02"))

    assert price == Decimal("98.00")


def test_stop_loss_price_above_entry_for_short() -> None:
    price = calculate_stop_loss_price(entry_price=Decimal("100"), side=OrderSide.SELL, stop_loss_pct=Decimal("0.02"))

    assert price == Decimal("102.00")


def test_stop_loss_price_rejects_non_positive_entry() -> None:
    with pytest.raises(ValidationError):
        calculate_stop_loss_price(entry_price=Decimal("0"), side=OrderSide.BUY, stop_loss_pct=Decimal("0.02"))


def test_stop_loss_price_rejects_out_of_range_pct() -> None:
    with pytest.raises(ValidationError):
        calculate_stop_loss_price(entry_price=Decimal("100"), side=OrderSide.BUY, stop_loss_pct=Decimal("1"))


def test_take_profit_price_uses_default_reward_risk_ratio_for_long() -> None:
    price = calculate_take_profit_price(entry_price=Decimal("100"), side=OrderSide.BUY, stop_loss_price=Decimal("98"))

    # risk = 2, default reward:risk = 2:1 -> reward = 4
    assert price == Decimal("104")


def test_take_profit_price_for_short() -> None:
    price = calculate_take_profit_price(
        entry_price=Decimal("100"), side=OrderSide.SELL, stop_loss_price=Decimal("102")
    )

    assert price == Decimal("96")


def test_take_profit_price_rejects_equal_entry_and_stop() -> None:
    with pytest.raises(ValidationError):
        calculate_take_profit_price(entry_price=Decimal("100"), side=OrderSide.BUY, stop_loss_price=Decimal("100"))


def test_position_size_risks_exactly_the_configured_fraction_of_equity() -> None:
    quantity = calculate_position_size(
        equity=Decimal("10000"),
        risk_per_trade_pct=Decimal("0.01"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("98"),
    )

    # Risking 1% of 10000 = 100, over a 2-unit-wide stop -> 50 units.
    assert quantity == Decimal("50")


def test_position_size_is_zero_when_equity_is_non_positive() -> None:
    quantity = calculate_position_size(
        equity=Decimal("0"),
        risk_per_trade_pct=Decimal("0.01"),
        entry_price=Decimal("100"),
        stop_loss_price=Decimal("98"),
    )

    assert quantity == Decimal("0")


def test_position_size_rejects_equal_entry_and_stop() -> None:
    with pytest.raises(ValidationError):
        calculate_position_size(
            equity=Decimal("10000"),
            risk_per_trade_pct=Decimal("0.01"),
            entry_price=Decimal("100"),
            stop_loss_price=Decimal("100"),
        )
