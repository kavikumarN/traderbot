from __future__ import annotations

from enum import StrEnum


class RiskRuleType(StrEnum):
    MAX_POSITION_NOTIONAL = "MAX_POSITION_NOTIONAL"
    MAX_DAILY_LOSS = "MAX_DAILY_LOSS"
    MAX_ORDER_RATE = "MAX_ORDER_RATE"
    SYMBOL_WHITELIST = "SYMBOL_WHITELIST"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    MAX_LEVERAGE = "MAX_LEVERAGE"
    # Phase 8 additions.
    MAX_OPEN_TRADES = "MAX_OPEN_TRADES"
    MAX_PORTFOLIO_EXPOSURE = "MAX_PORTFOLIO_EXPOSURE"
    RISK_PER_TRADE = "RISK_PER_TRADE"
    # threshold = drawdown_pct that triggers de-risking;
    # config.size_multiplier (default 0.5) = the size cut applied to
    # `RiskEngine.suggest_position_size` once triggered. Unlike MAX_DRAWDOWN
    # (which halts trading outright), this scales sizing down and stays in
    # effect until a human re-arms it — see `RiskState.de_risked`.
    DRAWDOWN_DERISK = "DRAWDOWN_DERISK"


class CircuitBreakerState(StrEnum):
    """The account-wide automatic kill switch. `CLOSED` means orders flow
    normally (a closed circuit conducts); `OPEN` means `RiskEngine` blocks
    every new order until the cooldown configured on the trip expires or an
    operator resets it early — the same "circuit breaker" vocabulary used
    for exchange-wide trading halts."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
