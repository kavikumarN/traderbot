from __future__ import annotations

import pytest

from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import UnknownStrategyTypeError
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin
from app.domain.strategy.plugin_manager import PluginManager


class _BasePlugin(StrategyPlugin):
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


class _PluginA(_BasePlugin):
    strategy_type = "TYPE_A"


class _PluginAAlternate(_BasePlugin):
    strategy_type = "TYPE_A"


class _PluginB(_BasePlugin):
    strategy_type = "TYPE_B"


class TestPluginManager:
    def test_register_then_get_roundtrip(self) -> None:
        manager = PluginManager()
        manager.register(_PluginA)
        assert manager.get("TYPE_A") is _PluginA

    def test_get_unknown_strategy_type_raises(self) -> None:
        manager = PluginManager()
        with pytest.raises(UnknownStrategyTypeError):
            manager.get("NOPE")

    def test_reregistering_same_class_is_idempotent(self) -> None:
        manager = PluginManager()
        manager.register(_PluginA)
        manager.register(_PluginA)
        assert manager.get("TYPE_A") is _PluginA

    def test_registering_different_class_under_same_type_raises(self) -> None:
        manager = PluginManager()
        manager.register(_PluginA)
        with pytest.raises(ValueError):
            manager.register(_PluginAAlternate)

    def test_list_available_returns_sorted_strategy_types(self) -> None:
        manager = PluginManager()
        manager.register(_PluginB)
        manager.register(_PluginA)
        assert manager.list_available() == ["TYPE_A", "TYPE_B"]
