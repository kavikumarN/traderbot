"""Backtest Engine: replays a chronological list of historical `Candle`s
through a real, initialized `StrategyPlugin` and simulates fills against a
synthetic cash/position book — no exchange, no `SignalManager`, no
`TradingService`, no DB writes per candle. `RunBacktestUseCase` is the only
caller; this class owns none of the persistence or candle-sourcing, just
the replay loop and the fill/equity bookkeeping.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.backtesting.analytics import (
    BacktestResult,
    EquityPoint,
    Fill,
    PositionState,
    compute_max_drawdown,
    compute_sharpe_ratio,
    compute_win_rate,
    simulate_fill,
)
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.plugin import StrategyPlugin


class BacktestEngine:
    async def run(
        self,
        plugin: StrategyPlugin,
        candles: list[Candle],
        *,
        initial_balance: Decimal,
        commission_rate: Decimal,
        periods_per_year: Decimal,
    ) -> BacktestResult:
        position = PositionState()
        cash = initial_balance
        fills: list[Fill] = []
        equity_points: list[EquityPoint] = []

        for candle in candles:
            await plugin.on_candle(candle)
            proposal = plugin.generate_signal()

            if proposal is not None:
                price = proposal.target_price if proposal.target_price is not None else candle.close
                simulated = simulate_fill(
                    position,
                    cash,
                    side=proposal.side,
                    price=price,
                    quantity=proposal.quantity,
                    commission_rate=commission_rate,
                )
                position = simulated.position
                cash = simulated.cash
                fills.append(
                    Fill(
                        executed_at=candle.close_time,
                        side=proposal.side,
                        price=price,
                        quantity=proposal.quantity,
                        commission=simulated.commission,
                        realized_pnl=simulated.realized_pnl,
                        cash_after=cash,
                        position_after=position.quantity,
                        reason=proposal.reason,
                    )
                )

            equity_points.append(
                EquityPoint(time=candle.close_time, equity=cash + position.quantity * candle.close)
            )

        final_balance = equity_points[-1].equity if equity_points else initial_balance
        equities = [point.equity for point in equity_points]
        total_return_pct = (
            (final_balance - initial_balance) / initial_balance if initial_balance != 0 else Decimal(0)
        )

        return BacktestResult(
            fills=fills,
            equity_curve=equity_points,
            final_balance=final_balance,
            total_return_pct=total_return_pct,
            sharpe_ratio=compute_sharpe_ratio(equities, periods_per_year=periods_per_year),
            max_drawdown_pct=compute_max_drawdown(equities),
            win_rate=compute_win_rate(fills),
            total_trades=len(fills),
        )
