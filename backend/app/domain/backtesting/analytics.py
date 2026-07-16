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

Order simulation (`PendingEntryOrder`, `PositionBracket`, and the
`apply_slippage`/`update_trailing_stop`/`check_bracket_trigger`/
`limit_order_touched`/`capped_fill_quantity` functions below) exists only
because candles carry OHLCV, not a real order book — every rule here is a
documented simplification, not a claim of perfect exchange fidelity:

* A limit order "touches" if the candle's low/high range crosses its price
  at any point during the candle — there's no way to know from OHLC alone
  whether it would have actually traded there (queue position, depth), so
  this is deliberately optimistic.
* A resting limit order can fill at most `_MAX_LIMIT_FILL_VOLUME_FRACTION`
  of a candle's own traded volume per candle (a common backtesting
  heuristic standing in for real depth data) — the rest stays pending into
  the next candle.
* Stop-loss/take-profit/trailing-stop always close the *entire* position in
  one fill — no partial bracket exits.
* If both a stop and a take-profit could trigger within the same candle,
  the stop is assumed to have hit first (the conservative assumption —
  otherwise a backtest would systematically overstate performance on wide
  candles that swing through both levels).
* Slippage worsens every market-style fill (entries, stop/take-profit/
  trailing exits) by a fixed `slippage_bps`; limit fills never slip past
  their own limit price, by definition of what a limit order is.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval, OrderSide
from app.domain.exchange.models.market_data import Candle

MAX_BACKTEST_CANDLES = 20_000

#: Fraction of a single candle's traded volume a resting limit order may
#: consume in that candle — see the module docstring.
MAX_LIMIT_FILL_VOLUME_FRACTION = Decimal("0.1")

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
class PendingEntryOrder:
    """A resting `OrderType.LIMIT` entry the engine hasn't (fully) filled
    yet — replaced wholesale by any newer signal, matching `StrategyPlugin.
    _emit`'s "replaces, doesn't accumulate" semantics for `_pending_signal`.
    The bracket fields ride along so that if/when this order fills, the
    resulting position immediately gets the stop/take-profit/trailing-stop
    its originating signal asked for."""

    side: OrderSide
    remaining_quantity: Decimal
    limit_price: Decimal
    stop_loss_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    trailing_stop_pct: Decimal | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class PositionBracket:
    """Stop-loss/take-profit/trailing-stop attached to the currently open
    position. `trailing_stop_price` is the live, ratcheted stop level once
    `trailing_stop_pct` is set — `None` until the first candle after entry
    computes it. A `trailing_stop_pct` fully replaces `stop_loss_price` as
    the operative stop (see `check_bracket_trigger`); the two aren't
    layered."""

    stop_loss_price: Decimal | None = None
    take_profit_price: Decimal | None = None
    trailing_stop_pct: Decimal | None = None
    trailing_stop_price: Decimal | None = None

    @property
    def is_empty(self) -> bool:
        return self.stop_loss_price is None and self.take_profit_price is None and self.trailing_stop_pct is None


@dataclass(frozen=True, slots=True)
class TradeStats:
    """Per-trade statistics derived from realized fills (those that closed
    or reduced a position — see `compute_win_rate`'s docstring for why
    opening/extending fills, which carry a `0` realized pnl, are excluded)."""

    expectancy: Decimal = Decimal(0)
    avg_win: Decimal = Decimal(0)
    avg_loss: Decimal = Decimal(0)
    largest_win: Decimal = Decimal(0)
    largest_loss: Decimal = Decimal(0)
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0


@dataclass(frozen=True, slots=True)
class BacktestResult:
    fills: list[Fill] = field(default_factory=list)
    equity_curve: list[EquityPoint] = field(default_factory=list)
    final_balance: Decimal = Decimal(0)
    total_return_pct: Decimal = Decimal(0)
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    calmar_ratio: Decimal | None = None
    cagr_pct: Decimal | None = None
    max_drawdown_pct: Decimal = Decimal(0)
    avg_drawdown_pct: Decimal = Decimal(0)
    win_rate: Decimal = Decimal(0)
    profit_factor: Decimal | None = None
    trade_stats: TradeStats = field(default_factory=TradeStats)
    exposure_pct: Decimal = Decimal(0)
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


def apply_slippage(price: Decimal, side: OrderSide, *, slippage_bps: Decimal) -> Decimal:
    """Worsens `price` for the trader — higher for a `BUY`, lower for a
    `SELL` — by `slippage_bps` basis points. Only market-style fills
    (entries, stop/take-profit/trailing exits) go through this; a limit
    order fills exactly at its own limit price by definition."""

    factor = Decimal(1) + slippage_bps / Decimal(10_000)
    return price * factor if side == OrderSide.BUY else price / factor


def limit_order_touched(order: PendingEntryOrder, candle: Candle) -> bool:
    """A `BUY` limit rests below the market and fills when price dips down
    to meet it (`candle.low <= limit_price`); a `SELL` limit rests above and
    fills on a rally up to it (`candle.high >= limit_price`)."""

    if order.side == OrderSide.BUY:
        return candle.low <= order.limit_price
    return candle.high >= order.limit_price


def capped_fill_quantity(remaining: Decimal, candle: Candle) -> Decimal:
    """How much of a resting limit order's `remaining` quantity this candle
    can plausibly have filled, capped at `MAX_LIMIT_FILL_VOLUME_FRACTION` of
    the candle's own traded volume — see the module docstring. `0` on a
    zero-volume candle (nothing traded, so nothing could have filled)."""

    if candle.volume <= 0:
        return Decimal(0)
    return min(remaining, candle.volume * MAX_LIMIT_FILL_VOLUME_FRACTION)


def update_trailing_stop(bracket: PositionBracket, position_side: OrderSide, candle: Candle) -> PositionBracket:
    """Ratchets `trailing_stop_price` in the position's favor using this
    candle's high (long) or low (short) — ratchets only, so a pullback
    never loosens a stop that already tightened. No-op if `trailing_stop_pct`
    isn't set on this bracket."""

    if bracket.trailing_stop_pct is None:
        return bracket

    if position_side == OrderSide.BUY:
        candidate = candle.high * (Decimal(1) - bracket.trailing_stop_pct)
        new_level = candidate if bracket.trailing_stop_price is None else max(bracket.trailing_stop_price, candidate)
    else:
        candidate = candle.low * (Decimal(1) + bracket.trailing_stop_pct)
        new_level = candidate if bracket.trailing_stop_price is None else min(bracket.trailing_stop_price, candidate)

    return replace(bracket, trailing_stop_price=new_level)


def check_bracket_trigger(
    bracket: PositionBracket, position_side: OrderSide, candle: Candle
) -> tuple[str, Decimal] | None:
    """Returns `(reason, trigger_price)` — `reason` one of `"stop_loss"`,
    `"trailing_stop"`, `"take_profit"` — if this candle's OHLC range touches
    an active bracket level, else `None`. A `trailing_stop_pct` bracket
    checks `trailing_stop_price` (already ratcheted by `update_trailing_stop`
    for this candle) instead of `stop_loss_price`; a stop and a take-profit
    are never both reported for the same candle — the stop wins (see module
    docstring)."""

    if position_side == OrderSide.BUY:
        stop_price = bracket.trailing_stop_price if bracket.trailing_stop_pct is not None else bracket.stop_loss_price
        if stop_price is not None and candle.low <= stop_price:
            reason = "trailing_stop" if bracket.trailing_stop_pct is not None else "stop_loss"
            return reason, stop_price
        if bracket.take_profit_price is not None and candle.high >= bracket.take_profit_price:
            return "take_profit", bracket.take_profit_price
    else:
        stop_price = bracket.trailing_stop_price if bracket.trailing_stop_pct is not None else bracket.stop_loss_price
        if stop_price is not None and candle.high >= stop_price:
            reason = "trailing_stop" if bracket.trailing_stop_pct is not None else "stop_loss"
            return reason, stop_price
        if bracket.take_profit_price is not None and candle.low <= bracket.take_profit_price:
            return "take_profit", bracket.take_profit_price

    return None


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

    returns = [(curr - prev) / prev for prev, curr in zip(equities, equities[1:], strict=False) if prev != 0]
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


def compute_avg_drawdown(equities: list[Decimal]) -> Decimal:
    """Mean of the drawdown series (peak-to-current at every point, `0` on
    fresh highs) — a gentler companion to `compute_max_drawdown`'s worst
    case, showing how deep underwater the equity curve sits on average."""

    if not equities:
        return Decimal(0)

    peak = equities[0]
    drawdowns: list[Decimal] = []
    for equity in equities:
        peak = max(peak, equity)
        if peak > 0:
            drawdowns.append((peak - equity) / peak)
    return sum(drawdowns) / len(drawdowns) if drawdowns else Decimal(0)


def compute_sortino_ratio(equities: list[Decimal], *, periods_per_year: Decimal) -> Decimal | None:
    """Same shape as `compute_sharpe_ratio` but penalizes only downside
    volatility: the denominator is the root-mean-square of *negative*
    per-candle returns (a 0% minimum-acceptable-return Sortino), so a
    strategy with big up-swings and small, steady losses scores higher here
    than on Sharpe alone."""

    if len(equities) < 3:
        return None

    returns = [(curr - prev) / prev for prev, curr in zip(equities, equities[1:], strict=False) if prev != 0]
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    downside_variance = sum(min(r, Decimal(0)) ** 2 for r in returns) / len(returns)
    if downside_variance <= 0:
        return None

    return (mean_return / downside_variance.sqrt()) * periods_per_year.sqrt()


def compute_cagr(equities: list[Decimal], *, periods_per_year: Decimal) -> Decimal | None:
    """Compound annual growth rate, annualized off the backtest's own
    candle cadence (`periods_per_year`) rather than assuming daily bars —
    same reasoning as `compute_sharpe_ratio`. `None` if there's too little
    history or the curve starts at (or crosses) zero/negative equity, where
    a compound growth rate isn't meaningful."""

    if len(equities) < 2 or equities[0] <= 0 or equities[-1] <= 0:
        return None

    years = Decimal(len(equities) - 1) / periods_per_year
    if years <= 0:
        return None

    return (equities[-1] / equities[0]) ** (Decimal(1) / years) - Decimal(1)


def compute_calmar_ratio(cagr_pct: Decimal | None, max_drawdown_pct: Decimal) -> Decimal | None:
    """CAGR per unit of worst-case pain (`max_drawdown_pct`) — `None` when
    CAGR itself is undefined or there's no drawdown to divide by (a
    perfectly monotonic equity curve has no meaningful Calmar ratio)."""

    if cagr_pct is None or max_drawdown_pct == 0:
        return None
    return cagr_pct / max_drawdown_pct


def compute_profit_factor(fills: list[Fill]) -> Decimal | None:
    """Gross profit / gross loss among realized fills. `None` (undefined,
    not infinite) when there are no realized fills at all, or no losing
    ones to divide by."""

    realized = [f.realized_pnl for f in fills if f.realized_pnl != 0]
    if not realized:
        return None

    gross_profit = sum((pnl for pnl in realized if pnl > 0), Decimal(0))
    gross_loss = sum((-pnl for pnl in realized if pnl < 0), Decimal(0))
    if gross_loss == 0:
        return None
    return gross_profit / gross_loss


def compute_trade_stats(fills: list[Fill]) -> TradeStats:
    """Expectancy, average/largest win & loss, and longest winning/losing
    streaks — all derived from the same realized-fills sequence `
    compute_win_rate`/`compute_profit_factor` use, walked once in fill
    (chronological) order so the streak counters see trades in the order
    they actually happened."""

    realized = [f.realized_pnl for f in fills if f.realized_pnl != 0]
    if not realized:
        return TradeStats()

    wins = [pnl for pnl in realized if pnl > 0]
    losses = [pnl for pnl in realized if pnl < 0]

    max_consecutive_wins = 0
    max_consecutive_losses = 0
    current_streak = 0
    current_sign = 0
    for pnl in realized:
        sign = 1 if pnl > 0 else -1
        current_streak = current_streak + 1 if sign == current_sign else 1
        current_sign = sign
        if sign > 0:
            max_consecutive_wins = max(max_consecutive_wins, current_streak)
        else:
            max_consecutive_losses = max(max_consecutive_losses, current_streak)

    return TradeStats(
        expectancy=sum(realized, Decimal(0)) / len(realized),
        avg_win=sum(wins, Decimal(0)) / len(wins) if wins else Decimal(0),
        avg_loss=sum(losses, Decimal(0)) / len(losses) if losses else Decimal(0),
        largest_win=max(wins, default=Decimal(0)),
        largest_loss=min(losses, default=Decimal(0)),
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
    )
