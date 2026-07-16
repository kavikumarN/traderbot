"""Backtest simulation math: pure functions, no I/O, no `UnitOfWork` — same
spirit as `app.domain.risk.position_sizing` and `app.domain.portfolio.
analytics`. `BacktestEngine` supplies the candle-by-candle signal stream;
this module turns a sequence of fills into a trade log, an equity curve,
and the Sharpe ratio / drawdown / win-rate figures derived from it.

`simulate_fill` mirrors `TradingService._apply_fill_to_existing_position`'s
weighted-average-cost accounting (the same algorithm live trading uses for
real fills) — reimplemented here since that one is private to
`trading_service.py`, same reasoning as `domain.portfolio.analytics.
replay_realized_pnl` in Phase 9. Sharpe/drawdown are the same *shape* as
Phase 9's portfolio versions but deliberately not shared with them:
annualization depends on how many candles-per-year the backtest's own
`KlineInterval` implies, not a fixed daily cadence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval, OrderSide

MAX_BACKTEST_CANDLES = 20_000

PERIODS_PER_YEAR: dict[KlineInterval, Decimal] = {
    KlineInterval.ONE_MINUTE: Decimal(365 * 24 * 60),
    KlineInterval.THREE_MINUTES: Decimal(365 * 24 * 20),
    KlineInterval.FIVE_MINUTES: Decimal(365 * 24 * 12),
    KlineInterval.FIFTEEN_MINUTES: Decimal(365 * 24 * 4),
    KlineInterval.THIRTY_MINUTES: Decimal(365 * 24 * 2),
    KlineInterval.ONE_HOUR: Decimal(365 * 24),
    KlineInterval.TWO_HOURS: Decimal(365 * 12),
    KlineInterval.FOUR_HOURS: Decimal(365 * 6),
    KlineInterval.SIX_HOURS: Decimal(365 * 4),
    KlineInterval.EIGHT_HOURS: Decimal(365 * 3),
    KlineInterval.TWELVE_HOURS: Decimal(365 * 2),
    KlineInterval.ONE_DAY: Decimal(365),
    KlineInterval.THREE_DAYS: Decimal(365) / Decimal(3),
    KlineInterval.ONE_WEEK: Decimal(52),
    KlineInterval.ONE_MONTH: Decimal(12),
}


@dataclass(frozen=True, slots=True)
class PositionState:
    quantity: Decimal = Decimal(0)
    avg_entry_price: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class SimulatedFill:
    position: PositionState
    cash: Decimal
    realized_pnl: Decimal
    commission: Decimal


@dataclass(frozen=True, slots=True)
class Fill:
    executed_at: datetime
    side: OrderSide
    price: Decimal
    quantity: Decimal
    commission: Decimal
    realized_pnl: Decimal
    cash_after: Decimal
    position_after: Decimal
    reason: str = ""


@dataclass(frozen=True, slots=True)
class EquityPoint:
    time: datetime
    equity: Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    fills: list[Fill] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    final_balance: Decimal = Decimal(0)
    total_return_pct: Decimal = Decimal(0)
    sharpe_ratio: Decimal | None = None
    max_drawdown_pct: Decimal = Decimal(0)
    win_rate: Decimal = Decimal(0)
    total_trades: int = 0


def simulate_fill(
    position: PositionState,
    cash: Decimal,
    *,
    side: OrderSide,
    price: Decimal,
    quantity: Decimal,
    commission_rate: Decimal,
) -> SimulatedFill:
    """A fill in the same direction as the open position extends it
    (blending the entry price); a fill against it closes/reduces (realizing
    pnl at the fill price) and, if it overshoots, flips the position onto
    the new side at the fill's price. Commission is charged in cash on
    every fill, win or lose."""

    signed_quantity = quantity if side == OrderSide.BUY else -quantity
    same_direction = position.quantity == 0 or (position.quantity > 0) == (signed_quantity > 0)
    new_quantity = position.quantity + signed_quantity

    if same_direction:
        total_cost = position.avg_entry_price * abs(position.quantity) + price * quantity
        new_avg_entry_price = total_cost / abs(new_quantity) if new_quantity != 0 else Decimal(0)
        realized_pnl = Decimal(0)
    else:
        closing_quantity = min(abs(signed_quantity), abs(position.quantity))
        direction = Decimal(1) if position.quantity > 0 else Decimal(-1)
        realized_pnl = direction * (price - position.avg_entry_price) * closing_quantity
        flipped = (new_quantity > 0) != (position.quantity > 0) and new_quantity != 0
        new_avg_entry_price = price if flipped else position.avg_entry_price

    new_position = PositionState(
        quantity=new_quantity, avg_entry_price=new_avg_entry_price if new_quantity != 0 else Decimal(0)
    )

    commission = price * quantity * commission_rate
    new_cash = cash - signed_quantity * price - commission

    return SimulatedFill(position=new_position, cash=new_cash, realized_pnl=realized_pnl, commission=commission)


def compute_max_drawdown(equities: list[Decimal]) -> Decimal:
    """Largest peak-to-trough decline across the equity curve, as a
    positive fraction. `0` for an empty or ever-rising curve."""

    if not equities:
        return Decimal(0)

    peak = equities[0]
    max_drawdown = Decimal(0)
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return max_drawdown


def compute_sharpe_ratio(equities: list[Decimal], *, periods_per_year: Decimal) -> Decimal | None:
    """Annualized Sharpe ratio from the equity curve's per-candle returns.
    `None` (undefined) rather than `0` when there's too little history or
    the returns have no variance to divide by."""

    if len(equities) < 3:
        return None

    returns = [(curr - prev) / prev for prev, curr in zip(equities, equities[1:]) if prev != 0]
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    if variance <= 0:
        return None

    return (mean_return / variance.sqrt()) * periods_per_year.sqrt()


def compute_win_rate(fills: list[Fill]) -> Decimal:
    """Winners / (winners + losers) among fills that actually realized a
    pnl (closed or reduced a position) — opening/extending fills carry a
    `0` realized pnl and don't count either way. `0` if nothing ever
    closed."""

    realized = [f for f in fills if f.realized_pnl != 0]
    if not realized:
        return Decimal(0)
    winners = sum(1 for f in realized if f.realized_pnl > 0)
    return Decimal(winners) / Decimal(len(realized))
