"""Built-in strategy plugins.

Importing this package registers every one of them against
`app.domain.strategy.plugin_manager.default_plugin_manager` (each module
below decorates its class with `@register_strategy` at import time) — the
"plugin loading" bootstrap. Anything that needs the built-in catalog
available (`StrategyLoader`, the API layer's plugin-type listing, the
engine at startup) imports this package first specifically to trigger that
registration; the module itself has no other side effects.
"""

from __future__ import annotations

from app.domain.strategy.plugins.breakout_strategy import BreakoutStrategy
from app.domain.strategy.plugins.ema_strategy import EmaCrossoverStrategy
from app.domain.strategy.plugins.grid_strategy import GridStrategy
from app.domain.strategy.plugins.macd_strategy import MacdStrategy
from app.domain.strategy.plugins.rsi_strategy import RsiStrategy
from app.domain.strategy.plugins.vwap_strategy import VwapMeanReversionStrategy

__all__ = [
    "BreakoutStrategy",
    "EmaCrossoverStrategy",
    "GridStrategy",
    "MacdStrategy",
    "RsiStrategy",
    "VwapMeanReversionStrategy",
]
