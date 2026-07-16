"""Backtest Engine: replays a chronological list of historical `Candle`s
through a real, initialized `StrategyPlugin` and simulates fills against a
synthetic cash/position book — no exchange, no `SignalManager`, no
`TradingService`, no DB writes per candle. `RunBacktestUseCase` is the only
caller; this class owns none of the persistence or candle-sourcing, just
the replay loop and the fill/equity bookkeeping.

Per candle, in this order: (1) an open position's stop-loss/take-profit/
trailing-stop is checked and, if triggered, closes the whole position —
resting protective orders are assumed to have already been "on the books"
before this candle opened; (2) a resting `LIMIT` entry order is checked for
a touch and (partially) filled; (3) the plugin sees the candle and may emit
a new signal, which either fills immediately (`MARKET`) or replaces the
resting limit order (`LIMIT`). See `domain.backtesting.analytics`'s module
docstring for the full set of simplifying assumptions behind all of this —
none of it claims real order-book fidelity, only a materially more
realistic approximation than "everything fills instantly at the signal
price."
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.domain.backtesting.analytics import (
    BacktestResult,
    EquityPoint,
    Fill,
    PendingEntryOrder,
    PositionBracket,
    PositionState,
    apply_slippage,
    capped_fill_quantity,
    check_bracket_trigger,
    compute_avg_drawdown,
    compute_cagr,
    compute_calmar_ratio,
    compute_max_drawdown,
    compute_profit_factor,
    compute_sharpe_ratio,
    compute_sortino_ratio,
    compute_trade_stats,
    compute_win_rate,
    limit_order_touched,
    simulate_fill,
    update_trailing_stop,
)
from app.domain.exchange.enums import OrderSide, OrderType
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.plugin import SignalProposal, StrategyPlugin


class BacktestEngine:
    async def run(
        self,
        plugin: StrategyPlugin,
        candles: list[Candle],
        *,
        initial_balance: Decimal,
        commission_rate: Decimal,
        periods_per_year: Decimal,
        slippage_bps: Decimal = Decimal(0),
    ) -> BacktestResult:
        position = PositionState()
        cash = initial_balance
        fills: list[Fill] = []
        equity_points: list[EquityPoint] = []
        candles_in_position = 0
        pending_entry: PendingEntryOrder | None = None
        bracket: PositionBracket | None = None

        for candle in candles:
            if position.quantity != 0 and bracket is not None and not bracket.is_empty:
                position, cash, bracket, bracket_fill = self._check_bracket(
                    position, cash, bracket, candle, commission_rate=commission_rate, slippage_bps=slippage_bps
                )
                if bracket_fill is not None:
                    fills.append(bracket_fill)

            if pending_entry is not None:
                position, cash, pending_entry, bracket, entry_fill = self._check_pending_entry(
                    position, cash, pending_entry, candle, commission_rate=commission_rate
                )
                if entry_fill is not None:
                    fills.append(entry_fill)

            await plugin.on_candle(candle)
            proposal = plugin.generate_signal()

            if proposal is not None:
                if proposal.order_type == OrderType.LIMIT and proposal.target_price is not None:
                    pending_entry = PendingEntryOrder(
                        side=proposal.side,
                        remaining_quantity=proposal.quantity,
                        limit_price=proposal.target_price,
                        stop_loss_price=proposal.stop_loss_price,
                        take_profit_price=proposal.take_profit_price,
                        trailing_stop_pct=proposal.trailing_stop_pct,
                        reason=proposal.reason,
                    )
                else:
                    pending_entry = None
                    position, cash, bracket, signal_fill = self._fill_market_signal(
                        position, cash, proposal, candle, commission_rate=commission_rate, slippage_bps=slippage_bps
                    )
                    fills.append(signal_fill)

            equity_points.append(
                EquityPoint(time=candle.close_time, equity=cash + position.quantity * candle.close)
            )
            if position.quantity != 0:
                candles_in_position += 1

        final_balance = equity_points[-1].equity if equity_points else initial_balance
        equities = [point.equity for point in equity_points]
        total_return_pct = (
            (final_balance - initial_balance) / initial_balance if initial_balance != 0 else Decimal(0)
        )
        max_drawdown_pct = compute_max_drawdown(equities)
        cagr_pct = compute_cagr(equities, periods_per_year=periods_per_year)

        return BacktestResult(
            fills=fills,
            equity_curve=equity_points,
            final_balance=final_balance,
            total_return_pct=total_return_pct,
            sharpe_ratio=compute_sharpe_ratio(equities, periods_per_year=periods_per_year),
            sortino_ratio=compute_sortino_ratio(equities, periods_per_year=periods_per_year),
            calmar_ratio=compute_calmar_ratio(cagr_pct, max_drawdown_pct),
            cagr_pct=cagr_pct,
            max_drawdown_pct=max_drawdown_pct,
            avg_drawdown_pct=compute_avg_drawdown(equities),
            win_rate=compute_win_rate(fills),
            profit_factor=compute_profit_factor(fills),
            trade_stats=compute_trade_stats(fills),
            exposure_pct=Decimal(candles_in_position) / Decimal(len(candles)) if candles else Decimal(0),
            total_trades=len(fills),
        )

    def _check_bracket(
        self,
        position: PositionState,
        cash: Decimal,
        bracket: PositionBracket,
        candle: Candle,
        *,
        commission_rate: Decimal,
        slippage_bps: Decimal,
    ) -> tuple[PositionState, Decimal, PositionBracket | None, Fill | None]:
        position_side = OrderSide.BUY if position.quantity > 0 else OrderSide.SELL
        bracket = update_trailing_stop(bracket, position_side, candle)
        trigger = check_bracket_trigger(bracket, position_side, candle)
        if trigger is None:
            return position, cash, bracket, None

        reason, trigger_price = trigger
        closing_side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
        fill_price = apply_slippage(trigger_price, closing_side, slippage_bps=slippage_bps)
        quantity = abs(position.quantity)
        simulated = simulate_fill(
            position, cash, side=closing_side, price=fill_price, quantity=quantity, commission_rate=commission_rate
        )
        fill = Fill(
            executed_at=candle.close_time,
            side=closing_side,
            price=fill_price,
            quantity=quantity,
            commission=simulated.commission,
            realized_pnl=simulated.realized_pnl,
            cash_after=simulated.cash,
            position_after=simulated.position.quantity,
            reason=reason,
        )
        return simulated.position, simulated.cash, None, fill

    def _check_pending_entry(
        self,
        position: PositionState,
        cash: Decimal,
        pending_entry: PendingEntryOrder,
        candle: Candle,
        *,
        commission_rate: Decimal,
    ) -> tuple[PositionState, Decimal, PendingEntryOrder | None, PositionBracket | None, Fill | None]:
        if not limit_order_touched(pending_entry, candle):
            return position, cash, pending_entry, None, None

        fillable = capped_fill_quantity(pending_entry.remaining_quantity, candle)
        if fillable <= 0:
            return position, cash, pending_entry, None, None

        simulated = simulate_fill(
            position,
            cash,
            side=pending_entry.side,
            price=pending_entry.limit_price,
            quantity=fillable,
            commission_rate=commission_rate,
        )
        remaining = pending_entry.remaining_quantity - fillable
        partial = remaining > 0
        fill = Fill(
            executed_at=candle.close_time,
            side=pending_entry.side,
            price=pending_entry.limit_price,
            quantity=fillable,
            commission=simulated.commission,
            realized_pnl=simulated.realized_pnl,
            cash_after=simulated.cash,
            position_after=simulated.position.quantity,
            reason=f"{pending_entry.reason} (limit, partial)" if partial else f"{pending_entry.reason} (limit)",
        )
        next_pending = replace(pending_entry, remaining_quantity=remaining) if partial else None
        next_bracket = _bracket_from(pending_entry) if simulated.position.quantity != 0 else None
        return simulated.position, simulated.cash, next_pending, next_bracket, fill

    def _fill_market_signal(
        self,
        position: PositionState,
        cash: Decimal,
        proposal: SignalProposal,
        candle: Candle,
        *,
        commission_rate: Decimal,
        slippage_bps: Decimal,
    ) -> tuple[PositionState, Decimal, PositionBracket | None, Fill]:
        price = proposal.target_price if proposal.target_price is not None else candle.close
        fill_price = apply_slippage(price, proposal.side, slippage_bps=slippage_bps)
        simulated = simulate_fill(
            position,
            cash,
            side=proposal.side,
            price=fill_price,
            quantity=proposal.quantity,
            commission_rate=commission_rate,
        )
        fill = Fill(
            executed_at=candle.close_time,
            side=proposal.side,
            price=fill_price,
            quantity=proposal.quantity,
            commission=simulated.commission,
            realized_pnl=simulated.realized_pnl,
            cash_after=simulated.cash,
            position_after=simulated.position.quantity,
            reason=proposal.reason,
        )
        bracket = _bracket_from(proposal) if simulated.position.quantity != 0 else None
        return simulated.position, simulated.cash, bracket, fill


def _bracket_from(source: SignalProposal | PendingEntryOrder) -> PositionBracket | None:
    bracket = PositionBracket(
        stop_loss_price=source.stop_loss_price,
        take_profit_price=source.take_profit_price,
        trailing_stop_pct=source.trailing_stop_pct,
    )
    return None if bracket.is_empty else bracket
