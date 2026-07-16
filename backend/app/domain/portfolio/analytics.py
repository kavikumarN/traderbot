"""Portfolio performance math: pure functions, no I/O, no `UnitOfWork` —
same spirit as `app.domain.risk.position_sizing`. `PortfolioService`
supplies the trade history and today's true mark-to-market equity; this
module turns that into an equity curve and the Sharpe ratio / drawdown /
monthly-return figures derived from it.

There is no equity-snapshot table in this codebase (no scheduler
infrastructure exists to populate one), so the equity curve is instead
*derived* by replaying `trade_history` chronologically with the same
weighted-average-cost accounting `TradingService._apply_fill_to_existing_
position` applies live, then anchoring that replay to today's real equity.
This is a realized-only curve between trade days (unrealized mark-to-market
swings intra-day aren't captured) — an intentional simplification, not an
oversight.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.domain.exchange.enums import OrderSide
from app.domain.trading.entities import Trade

_ANNUALIZATION_DAYS = Decimal("365")  # crypto markets trade continuously, unlike TradFi's 252-day convention


@dataclass(frozen=True, slots=True)
class EquityPoint:
    date: date
    equity: Decimal
    realized_pnl_cum: Decimal
    fees_cum: Decimal


@dataclass(frozen=True, slots=True)
class MonthlyReturn:
    month: str  # "YYYY-MM"
    return_pct: Decimal
    pnl: Decimal


def replay_realized_pnl(trades: list[Trade]) -> list[tuple[Trade, Decimal, Decimal]]:
    """Replays every trade in chronological order using the same
    weighted-average-cost accounting `TradingService` applies live to the
    persisted `Position` rows, producing a `(trade, realized_pnl_delta,
    fee)` tuple per trade. Purely read-only — never touches a `Position`.
    """

    positions: dict[str, tuple[Decimal, Decimal]] = {}  # symbol -> (quantity, avg_entry_price)
    events: list[tuple[Trade, Decimal, Decimal]] = []

    for trade in sorted(trades, key=lambda t: t.executed_at):
        quantity, avg_entry_price = positions.get(trade.symbol, (Decimal(0), Decimal(0)))
        signed_quantity = trade.quantity if trade.side == OrderSide.BUY else -trade.quantity
        same_direction = quantity == 0 or (quantity > 0) == (signed_quantity > 0)
        new_quantity = quantity + signed_quantity

        if same_direction:
            total_cost = avg_entry_price * abs(quantity) + trade.price * trade.quantity
            new_avg_entry_price = total_cost / abs(new_quantity) if new_quantity != 0 else Decimal(0)
            realized_delta = Decimal(0)
        else:
            closing_quantity = min(abs(signed_quantity), abs(quantity))
            direction = Decimal(1) if quantity > 0 else Decimal(-1)
            realized_delta = direction * (trade.price - avg_entry_price) * closing_quantity
            flipped = (new_quantity > 0) != (quantity > 0) and new_quantity != 0
            new_avg_entry_price = trade.price if flipped else avg_entry_price

        positions[trade.symbol] = (new_quantity, new_avg_entry_price if new_quantity != 0 else Decimal(0))
        events.append((trade, realized_delta, trade.commission))

    return events


def build_equity_curve(trades: list[Trade], *, current_equity: Decimal, as_of: date) -> list[EquityPoint]:
    """One `EquityPoint` per calendar day from the first trade through
    `as_of`, forward-filled between trade days. Anchored so the *last*
    point always equals `current_equity` (today's true mark-to-market
    figure, including unrealized pnl on any still-open positions) —
    everything earlier is `current_equity` walked backward by the realized
    pnl/fee deltas the replay produced. Returns `[]` with no trade history.
    """

    events = replay_realized_pnl(trades)
    if not events:
        return []

    total_realized = sum((delta for _, delta, _ in events), Decimal(0))
    total_fees = sum((fee for _, _, fee in events), Decimal(0))
    starting_equity = current_equity - total_realized + total_fees

    daily_totals: dict[date, tuple[Decimal, Decimal]] = {}
    realized_cum = Decimal(0)
    fees_cum = Decimal(0)
    for trade, delta, fee in events:
        realized_cum += delta
        fees_cum += fee
        daily_totals[trade.executed_at.date()] = (realized_cum, fees_cum)

    first_day = min(daily_totals)
    last_day = max(first_day, as_of)

    points: list[EquityPoint] = []
    running_realized = Decimal(0)
    running_fees = Decimal(0)
    day = first_day
    while day <= last_day:
        if day in daily_totals:
            running_realized, running_fees = daily_totals[day]
        points.append(
            EquityPoint(
                date=day,
                equity=starting_equity + running_realized - running_fees,
                realized_pnl_cum=running_realized,
                fees_cum=running_fees,
            )
        )
        day += timedelta(days=1)

    # The realized-only projection for "today" won't reflect unrealized
    # pnl on any still-open position — replace just the final point with
    # the real, live mark-to-market figure the caller supplied.
    last = points[-1]
    points[-1] = EquityPoint(
        date=last.date, equity=current_equity, realized_pnl_cum=last.realized_pnl_cum, fees_cum=last.fees_cum
    )
    return points


def compute_sharpe_ratio(points: list[EquityPoint], *, risk_free_rate: Decimal = Decimal(0)) -> Decimal | None:
    """Annualized Sharpe ratio from the curve's daily returns. `None`
    (undefined) rather than `0` when there's too little history or the
    returns have no variance to divide by."""

    if len(points) < 3:
        return None

    returns = [
        (curr.equity - prev.equity) / prev.equity for prev, curr in zip(points, points[1:]) if prev.equity != 0
    ]
    if len(returns) < 2:
        return None

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
    if variance <= 0:
        return None

    daily_sharpe = (mean_return - risk_free_rate) / variance.sqrt()
    return daily_sharpe * _ANNUALIZATION_DAYS.sqrt()


def compute_max_drawdown(points: list[EquityPoint]) -> Decimal:
    """Largest peak-to-trough decline across the whole curve, as a
    positive fraction (`0.25` == a 25% drawdown). `0` for an empty or
    ever-rising curve."""

    if not points:
        return Decimal(0)

    peak = points[0].equity
    max_drawdown = Decimal(0)
    for point in points:
        peak = max(peak, point.equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - point.equity) / peak)
    return max_drawdown


def compute_current_drawdown(points: list[EquityPoint]) -> Decimal:
    """How far today's equity sits below the curve's all-time high, as a
    positive fraction. `0` if today's equity *is* the high-water mark."""

    if not points:
        return Decimal(0)

    peak = max(point.equity for point in points)
    if peak <= 0:
        return Decimal(0)
    return max(Decimal(0), (peak - points[-1].equity) / peak)


def bucket_monthly_returns(points: list[EquityPoint]) -> list[MonthlyReturn]:
    """One entry per calendar month present in the curve: the percentage
    (and absolute) change in equity from the last known value before that
    month to the last value within it. The very first month's baseline is
    the curve's own starting equity."""

    if not points:
        return []

    month_end_equity: dict[str, Decimal] = {}
    month_order: list[str] = []
    for point in points:
        key = f"{point.date.year:04d}-{point.date.month:02d}"
        if key not in month_end_equity:
            month_order.append(key)
        month_end_equity[key] = point.equity

    results: list[MonthlyReturn] = []
    previous_equity = points[0].equity
    for key in month_order:
        end_equity = month_end_equity[key]
        pnl = end_equity - previous_equity
        return_pct = pnl / previous_equity if previous_equity != 0 else Decimal(0)
        results.append(MonthlyReturn(month=key, return_pct=return_pct, pnl=pnl))
        previous_equity = end_equity
    return results
