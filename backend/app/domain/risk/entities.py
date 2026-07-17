"""Risk bounded context.

`RiskRule` rows are the persisted form of the composable Specification
pattern described in Phase 0 — each row is one clause (`MaxPositionSpec`,
`SymbolWhitelistSpec`, ...); a future risk-service ANDs together every
active rule that applies to a strategy (or the whole account, when
`strategy_id` is null) to decide whether a signal may proceed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.domain.exceptions import ValidationError
from app.domain.risk.enums import CircuitBreakerState, RiskRuleType

_THRESHOLD_REQUIRED_TYPES = frozenset(
    {
        RiskRuleType.MAX_POSITION_NOTIONAL,
        RiskRuleType.MAX_DAILY_LOSS,
        RiskRuleType.MAX_ORDER_RATE,
        RiskRuleType.MAX_DRAWDOWN,
        RiskRuleType.MAX_LEVERAGE,
        RiskRuleType.MAX_OPEN_TRADES,
        RiskRuleType.MAX_PORTFOLIO_EXPOSURE,
        RiskRuleType.RISK_PER_TRADE,
        RiskRuleType.DRAWDOWN_DERISK,
    }
)


@dataclass(slots=True)
class RiskRule:
    id: uuid.UUID
    user_id: uuid.UUID
    rule_type: RiskRuleType
    is_active: bool
    created_at: datetime
    updated_at: datetime
    strategy_id: uuid.UUID | None = None
    threshold: Decimal | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.rule_type in _THRESHOLD_REQUIRED_TYPES and self.threshold is None:
            raise ValidationError(f"{self.rule_type} requires a threshold")
        if self.rule_type == RiskRuleType.SYMBOL_WHITELIST and not self.config.get("symbols"):
            raise ValidationError("SYMBOL_WHITELIST requires config.symbols")

    @property
    def is_account_wide(self) -> bool:
        return self.strategy_id is None

    def applies_to(self, strategy_id: uuid.UUID) -> bool:
        return self.is_active and (self.is_account_wide or self.strategy_id == strategy_id)


@dataclass(slots=True)
class RiskState:
    """One user's live risk runtime state — the mutable counterpart to the
    static `RiskRule` specifications above. Where a `RiskRule` says *what*
    limit applies, `RiskState` tracks *where the account currently stands*
    against it: today's realized losses, the equity high-water mark
    drawdown is measured from, a streak of losing trades, and whether the
    account is currently halted (automatically, by the circuit breaker) or
    stopped (manually, by the emergency stop). `RiskEngine` is the only
    writer; everything else treats this as a read-mostly snapshot.

    Lazily created the first time `RiskEngine` evaluates a trade for a
    user — there is deliberately no "create risk state" use case, mirroring
    how `TradingService` lazily provisions a default `ExchangeAccount`.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    circuit_breaker: CircuitBreakerState
    updated_at: datetime
    circuit_breaker_reason: str | None = None
    circuit_breaker_tripped_at: datetime | None = None
    circuit_breaker_resume_at: datetime | None = None
    emergency_stop: bool = False
    emergency_stop_reason: str | None = None
    emergency_stop_at: datetime | None = None
    consecutive_losses: int = 0
    daily_loss: Decimal = field(default_factory=lambda: Decimal(0))
    daily_loss_date: date | None = None
    equity_peak: Decimal = field(default_factory=lambda: Decimal(0))
    # De-risking: a softer sibling of the circuit breaker. Where the circuit
    # breaker halts trading outright (and can auto-resume after a cooldown),
    # de-risking only scales `suggest_position_size` down by
    # `de_risk_multiplier` and, deliberately, never auto-clears — an
    # operator must call `rearm_de_risk` once they've reviewed the drawdown,
    # so an account can't silently creep back to full size while it's still
    # underwater.
    de_risked: bool = False
    de_risk_multiplier: Decimal = field(default_factory=lambda: Decimal(1))
    de_risk_reason: str | None = None
    de_risked_at: datetime | None = None

    @property
    def is_trading_allowed(self) -> bool:
        return self.circuit_breaker == CircuitBreakerState.CLOSED and not self.emergency_stop

    def roll_daily_window(self, today: date) -> None:
        """Today's loss counter only means something for today — a fresh
        UTC calendar day starts a fresh budget, same rollover semantics as
        an exchange's own daily-loss-limit rule."""
        if self.daily_loss_date != today:
            self.daily_loss_date = today
            self.daily_loss = Decimal(0)

    def auto_resume_if_due(self, now: datetime) -> None:
        """A tripped breaker whose cooldown has elapsed self-heals the next
        time it's consulted, rather than needing a background sweep — the
        same computed-expiry pattern `Signal.is_expired` uses."""
        if (
            self.circuit_breaker == CircuitBreakerState.OPEN
            and self.circuit_breaker_resume_at is not None
            and now >= self.circuit_breaker_resume_at
        ):
            self.reset_circuit_breaker()

    def trip_circuit_breaker(self, *, reason: str, now: datetime, resume_at: datetime | None) -> None:
        self.circuit_breaker = CircuitBreakerState.OPEN
        self.circuit_breaker_reason = reason
        self.circuit_breaker_tripped_at = now
        self.circuit_breaker_resume_at = resume_at

    def reset_circuit_breaker(self) -> None:
        self.circuit_breaker = CircuitBreakerState.CLOSED
        self.circuit_breaker_reason = None
        self.circuit_breaker_tripped_at = None
        self.circuit_breaker_resume_at = None

    def activate_emergency_stop(self, *, reason: str, now: datetime) -> None:
        self.emergency_stop = True
        self.emergency_stop_reason = reason
        self.emergency_stop_at = now

    def deactivate_emergency_stop(self) -> None:
        self.emergency_stop = False
        self.emergency_stop_reason = None
        self.emergency_stop_at = None

    def record_trade_result(self, realized_pnl_delta: Decimal) -> None:
        """Updates the loss streak/daily-loss counters a single fill's
        newly-realized pnl contributes. Callers must `roll_daily_window`
        first so a loss just after midnight lands in the right day."""
        if realized_pnl_delta < 0:
            self.daily_loss += -realized_pnl_delta
            self.consecutive_losses += 1
        elif realized_pnl_delta > 0:
            self.consecutive_losses = 0

    def update_equity_peak(self, current_equity: Decimal) -> None:
        if current_equity > self.equity_peak:
            self.equity_peak = current_equity

    def drawdown_pct(self, current_equity: Decimal) -> Decimal:
        if self.equity_peak <= 0:
            return Decimal(0)
        return max(Decimal(0), (self.equity_peak - current_equity) / self.equity_peak)

    def activate_de_risk(self, *, multiplier: Decimal, reason: str, now: datetime) -> None:
        self.de_risked = True
        self.de_risk_multiplier = multiplier
        self.de_risk_reason = reason
        self.de_risked_at = now

    def rearm_de_risk(self) -> None:
        self.de_risked = False
        self.de_risk_multiplier = Decimal(1)
        self.de_risk_reason = None
        self.de_risked_at = None
