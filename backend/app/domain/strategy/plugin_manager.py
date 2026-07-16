"""Plugin Manager: the strategy-type registry.

A `PluginManager` is a plain in-memory mapping from `strategy_type` string
(e.g. `"EMA_CROSSOVER"`) to the `StrategyPlugin` subclass that implements
it. It's a class, not a bare module-level dict, so tests can construct a
fresh, isolated one instead of sharing (and polluting) process-wide plugin
registrations — `default_plugin_manager` below is the process-wide instance
everything outside tests actually uses.

New strategies register themselves with `@register_strategy` at import
time (see any file under `app.domain.strategy.plugins`) — the "plugin"
half of "plugin-based": adding a seventh built-in strategy, or a
third-party one, means writing one more `StrategyPlugin` subclass and
decorating it, not touching this file or `StrategyLoader`.
"""

from __future__ import annotations

from app.domain.strategy.exceptions import UnknownStrategyTypeError
from app.domain.strategy.plugin import StrategyPlugin


class PluginManager:
    def __init__(self) -> None:
        self._plugins: dict[str, type[StrategyPlugin]] = {}

    def register(self, plugin_cls: type[StrategyPlugin]) -> type[StrategyPlugin]:
        strategy_type = plugin_cls.strategy_type
        existing = self._plugins.get(strategy_type)
        if existing is not None and existing is not plugin_cls:
            raise ValueError(
                f"Strategy type {strategy_type!r} is already registered to {existing.__name__}"
            )
        self._plugins[strategy_type] = plugin_cls
        return plugin_cls

    def get(self, strategy_type: str) -> type[StrategyPlugin]:
        try:
            return self._plugins[strategy_type]
        except KeyError:
            raise UnknownStrategyTypeError(strategy_type) from None

    def list_available(self) -> list[str]:
        return sorted(self._plugins)


#: Process-wide registry that `app.domain.strategy.plugins` populates on
#: import, and that `StrategyLoader` consults by default.
default_plugin_manager = PluginManager()


def register_strategy(plugin_cls: type[StrategyPlugin]) -> type[StrategyPlugin]:
    """Class decorator: `@register_strategy` on a `StrategyPlugin` subclass
    registers it against `default_plugin_manager`."""
    return default_plugin_manager.register(plugin_cls)
