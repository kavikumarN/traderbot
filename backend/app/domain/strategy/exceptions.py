"""Strategy-engine domain exceptions — subclass the shared `DomainError` so
the existing HTTP exception-handler pipeline (`app.interface.api.errors`)
picks them up automatically, same as `app.domain.trading.exceptions`.
"""

from __future__ import annotations

from app.domain.exceptions import DomainError


class UnknownStrategyTypeError(DomainError):
    """A `Strategy.config["strategy_type"]` doesn't match any plugin
    registered with the `PluginManager`."""

    def __init__(self, strategy_type: str) -> None:
        self.strategy_type = strategy_type
        super().__init__(f"Unknown strategy type: {strategy_type}")


class InvalidStrategyConfigError(DomainError):
    """A `Strategy.config` is missing a required key or has one of the
    wrong shape — raised either by `StrategyLoader` (structural: is there a
    `strategy_type`, is `parameters` an object) or by a plugin's own
    `initialize()` (semantic: does *this* strategy have the parameters it
    specifically needs)."""

    def __init__(self, strategy_type: str, reason: str) -> None:
        self.strategy_type = strategy_type
        self.reason = reason
        super().__init__(f"Invalid config for strategy type {strategy_type}: {reason}")
