"""The Strategy Engine's plugin contract.

`StrategyPlugin` is what every concrete strategy (EMA crossover, RSI, MACD,
VWAP, Grid, Breakout, ...) implements. It is intentionally free of any I/O,
persistence, or exchange dependency — a plugin only ever sees the market
data it's handed (`Ticker`/`Candle`) and its own `StrategyContext`, and only
ever hands back a `SignalProposal`. Everything about *what happens* with
that proposal — persisting it as a `Signal`, deciding whether to act on it,
placing an order — is the engine's/`SignalManager`'s job, not the plugin's.
That separation is what makes a plugin unit-testable with nothing but a
sequence of `Candle`/`Ticker` objects, and safe to run in paper or live
trading without knowing which one it's in.

Every concrete plugin implements all five lifecycle hooks explicitly
(`initialize`, `on_tick`, `on_candle`, `generate_signal`, `shutdown`), even
where a hook is a no-op for that strategy — each plugin file is then a
complete, self-contained description of the strategy's behavior, without a
reader needing to check this base class to know what a given method does.
`generate_signal` follows one shared pattern everywhere: `on_tick`/
`on_candle` are where a plugin actually decides "something just happened"
(a crossover, a breakout, a grid-line cross) and queues at most one
`SignalProposal` via `self._emit(...)`; `generate_signal()` itself is a
cheap, synchronous drain of whatever's queued — `self._drain_pending_signal()`
does that in one line, so every plugin's `generate_signal` is trivially
"return self._drain_pending_signal()".
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, ClassVar

from app.domain.exchange.enums import OrderSide
from app.domain.exchange.models.market_data import Candle, Ticker
from app.domain.strategy.exceptions import InvalidStrategyConfigError


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Everything a plugin instance needs at construction time — its own
    identity, the single symbol it trades, and its user-supplied parameters
    (validated by the plugin itself, not by this type)."""

    strategy_id: uuid.UUID
    symbol: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SignalProposal:
    """What a plugin hands back to the engine — deliberately smaller than
    the persisted `Signal` aggregate (no id, no strategy_id, no status):
    those are `SignalManager`'s concern, not the plugin's."""

    side: OrderSide
    quantity: Decimal
    target_price: Decimal | None = None
    reason: str = ""


class StrategyPlugin(ABC):
    #: Registry key this plugin is looked up by — see
    #: `app.domain.strategy.plugin_manager`. Every subclass must set this.
    strategy_type: ClassVar[str]

    def __init__(self, context: StrategyContext) -> None:
        self.context = context
        self._pending_signal: SignalProposal | None = None

    @abstractmethod
    async def initialize(self) -> None:
        """Called once by `StrategyLoader`, before any tick/candle is fed
        in. Validate `self.context.parameters` here and raise
        `InvalidStrategyConfigError` for anything missing/malformed —
        better to fail loudly at load time than silently on the first
        tick."""
        ...

    @abstractmethod
    async def on_tick(self, ticker: Ticker) -> None:
        """Called on every ticker update for `self.context.symbol`."""
        ...

    @abstractmethod
    async def on_candle(self, candle: Candle) -> None:
        """Called whenever a candle closes for `self.context.symbol`."""
        ...

    @abstractmethod
    def generate_signal(self) -> SignalProposal | None:
        """Called by the engine after every `on_tick`/`on_candle` — returns
        (and clears) whatever `on_tick`/`on_candle` most recently queued via
        `self._emit(...)`, or `None` if nothing is pending right now."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Called once when the strategy is paused/retired, or the engine
        itself stops. Release anything `initialize()` acquired."""
        ...

    # --- helpers for subclasses ------------------------------------------------------------

    def _emit(self, side: OrderSide, *, target_price: Decimal | None = None, reason: str = "") -> None:
        """Queues a signal for the next `generate_signal()` call. Replaces
        (doesn't accumulate) any signal already pending — a plugin only
        ever wants to act on its most current read of the market."""
        self._pending_signal = SignalProposal(
            side=side, quantity=self._quantity(), target_price=target_price, reason=reason
        )

    def _drain_pending_signal(self) -> SignalProposal | None:
        signal, self._pending_signal = self._pending_signal, None
        return signal

    def _quantity(self) -> Decimal:
        """Every built-in strategy trades a fixed lot size supplied in
        `parameters["quantity"]` — position sizing beyond that (e.g.
        risk-based sizing) is future work, not something this base class
        should guess at."""
        raw = self.context.parameters.get("quantity")
        if raw is None:
            raise InvalidStrategyConfigError(self.strategy_type, "parameters.quantity is required")
        try:
            quantity = Decimal(str(raw))
        except Exception as exc:
            raise InvalidStrategyConfigError(self.strategy_type, "parameters.quantity must be numeric") from exc
        if quantity <= 0:
            raise InvalidStrategyConfigError(self.strategy_type, "parameters.quantity must be positive")
        return quantity
