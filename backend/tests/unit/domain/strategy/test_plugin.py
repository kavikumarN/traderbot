from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.domain.exchange.enums import OrderSide, OrderType
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import SignalProposal, StrategyContext, StrategyPlugin


class _DummyPlugin(StrategyPlugin):
    strategy_type = "DUMMY"

    async def initialize(self) -> None:
        return None

    async def on_tick(self, ticker: Ticker) -> None:
        return None

    async def on_candle(self, candle: Candle) -> None:
        return None

    def generate_signal(self) -> SignalProposal | None:
        return self._drain_pending_signal()

    async def shutdown(self) -> None:
        return None


def make_plugin(**parameters: object) -> _DummyPlugin:
    context = StrategyContext(strategy_id=uuid.uuid4(), symbol="BTCUSDT", parameters=parameters)
    return _DummyPlugin(context)


class TestEmitAndDrain:
    def test_drain_without_emit_returns_none(self) -> None:
        plugin = make_plugin(quantity="1")
        assert plugin.generate_signal() is None

    def test_emit_then_drain_roundtrip(self) -> None:
        plugin = make_plugin(quantity="2")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"), reason="test reason")

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.side == OrderSide.BUY
        assert signal.quantity == Decimal("2")
        assert signal.target_price == Decimal("100")
        assert signal.reason == "test reason"

    def test_drain_clears_pending_signal(self) -> None:
        plugin = make_plugin(quantity="1")
        plugin._emit(OrderSide.BUY)
        plugin.generate_signal()
        assert plugin.generate_signal() is None

    def test_emit_twice_before_drain_replaces_not_accumulates(self) -> None:
        plugin = make_plugin(quantity="1")
        plugin._emit(OrderSide.BUY, reason="first")
        plugin._emit(OrderSide.SELL, reason="second")

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.side == OrderSide.SELL
        assert signal.reason == "second"
        assert plugin.generate_signal() is None

    def test_defaults_to_market_order_with_no_brackets(self) -> None:
        plugin = make_plugin(quantity="1")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"))

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.order_type == OrderType.MARKET
        assert signal.stop_loss_price is None
        assert signal.take_profit_price is None
        assert signal.trailing_stop_pct is None

    def test_explicit_order_type_is_passed_through(self) -> None:
        plugin = make_plugin(quantity="1")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"), order_type=OrderType.LIMIT)

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.order_type == OrderType.LIMIT


class TestBracketParameters:
    def test_stop_loss_and_take_profit_sit_on_opposite_sides_for_a_long_entry(self) -> None:
        plugin = make_plugin(quantity="1", stop_loss_pct="0.02", take_profit_pct="0.05")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"))

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.stop_loss_price == Decimal("98")  # 100 * (1 - 0.02)
        assert signal.take_profit_price == Decimal("105")  # 100 * (1 + 0.05)

    def test_stop_loss_and_take_profit_are_mirrored_for_a_short_entry(self) -> None:
        plugin = make_plugin(quantity="1", stop_loss_pct="0.02", take_profit_pct="0.05")
        plugin._emit(OrderSide.SELL, target_price=Decimal("100"))

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.stop_loss_price == Decimal("102")  # above entry for a short
        assert signal.take_profit_price == Decimal("95")  # below entry for a short

    def test_trailing_stop_pct_passes_through_unscaled(self) -> None:
        plugin = make_plugin(quantity="1", trailing_stop_pct="0.015")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"))

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.trailing_stop_pct == Decimal("0.015")

    def test_no_brackets_configured_leaves_them_none(self) -> None:
        plugin = make_plugin(quantity="1")
        plugin._emit(OrderSide.BUY, target_price=Decimal("100"))

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.stop_loss_price is None
        assert signal.take_profit_price is None
        assert signal.trailing_stop_pct is None

    def test_no_entry_price_means_no_brackets_even_if_configured(self) -> None:
        plugin = make_plugin(quantity="1", stop_loss_pct="0.02")
        plugin._emit(OrderSide.BUY)  # no target_price

        signal = plugin.generate_signal()

        assert signal is not None
        assert signal.stop_loss_price is None

    def test_non_numeric_bracket_parameter_raises(self) -> None:
        plugin = make_plugin(quantity="1", stop_loss_pct="not-a-number")
        with pytest.raises(InvalidStrategyConfigError):
            plugin._emit(OrderSide.BUY, target_price=Decimal("100"))

    def test_zero_bracket_parameter_raises(self) -> None:
        plugin = make_plugin(quantity="1", take_profit_pct="0")
        with pytest.raises(InvalidStrategyConfigError):
            plugin._emit(OrderSide.BUY, target_price=Decimal("100"))


class TestQuantity:
    def test_missing_quantity_raises(self) -> None:
        plugin = make_plugin()
        with pytest.raises(InvalidStrategyConfigError):
            plugin._quantity()

    def test_non_numeric_quantity_raises(self) -> None:
        plugin = make_plugin(quantity="not-a-number")
        with pytest.raises(InvalidStrategyConfigError):
            plugin._quantity()

    def test_zero_quantity_raises(self) -> None:
        plugin = make_plugin(quantity="0")
        with pytest.raises(InvalidStrategyConfigError):
            plugin._quantity()

    def test_negative_quantity_raises(self) -> None:
        plugin = make_plugin(quantity="-1")
        with pytest.raises(InvalidStrategyConfigError):
            plugin._quantity()

    def test_valid_quantity_returns_positive_decimal(self) -> None:
        plugin = make_plugin(quantity="2.5")
        assert plugin._quantity() == Decimal("2.5")
