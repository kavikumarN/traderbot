"""Strategy Loader: turns a persisted `Strategy` aggregate into a live,
initialized `StrategyPlugin` instance.

`Strategy.config` (a free-form JSONB blob — see `app.domain.strategy.entities`)
is expected to look like::

    {
        "strategy_type": "EMA_CROSSOVER",
        "parameters": {"fast_period": 12, "slow_period": 26, "quantity": "0.01"}
    }

`strategy_type` is resolved through a `PluginManager` (dependency-injected
so tests can supply one with only fake plugins registered, instead of the
process-wide built-in catalog); `parameters` is handed to the plugin
untouched via `StrategyContext` — each plugin validates its own required
keys in its own `initialize()`, this loader only validates the structural
shape (is there a type, is `parameters` an object) that's common to every
plugin.
"""

from __future__ import annotations

from typing import Any

from app.domain.strategy.entities import Strategy
from app.domain.strategy.exceptions import InvalidStrategyConfigError
from app.domain.strategy.plugin import StrategyContext, StrategyPlugin
from app.domain.strategy.plugin_manager import PluginManager, default_plugin_manager


class StrategyLoader:
    def __init__(self, plugin_manager: PluginManager = default_plugin_manager) -> None:
        self._plugin_manager = plugin_manager

    async def load(self, strategy: Strategy) -> StrategyPlugin:
        strategy_type = strategy.config.get("strategy_type")
        if not strategy_type or not isinstance(strategy_type, str):
            raise InvalidStrategyConfigError(str(strategy_type), "config.strategy_type is required")

        parameters: Any = strategy.config.get("parameters", {})
        if not isinstance(parameters, dict):
            raise InvalidStrategyConfigError(strategy_type, "config.parameters must be an object")

        plugin_cls = self._plugin_manager.get(strategy_type)
        plugin = plugin_cls(
            StrategyContext(strategy_id=strategy.id, symbol=strategy.symbol, parameters=parameters)
        )
        await plugin.initialize()
        return plugin
