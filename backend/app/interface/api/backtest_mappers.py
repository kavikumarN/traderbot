"""Domain `Backtest` -> API response mapping. `symbol`/`interval`/
`trade_log`/`equity_curve` all live inside `Backtest.results` (a free-form
JSONB blob — see `RunBacktestUseCase._result_to_dict`), not as columns on
the entity itself; this is the one place that shape is unpacked into the
typed response schemas."""

from __future__ import annotations

from app.domain.strategy.entities import Backtest
from app.interface.api.schemas.backtest import (
    BacktestEquityPointResponse,
    BacktestFillResponse,
    BacktestResponse,
)


def backtest_to_response(backtest: Backtest) -> BacktestResponse:
    results = backtest.results
    return BacktestResponse(
        id=backtest.id,
        strategy_id=backtest.strategy_id,
        status=backtest.status.value,
        period_start=backtest.period_start,
        period_end=backtest.period_end,
        symbol=results.get("symbol", ""),
        interval=results.get("interval", ""),
        initial_balance=str(backtest.initial_balance),
        final_balance=str(backtest.final_balance) if backtest.final_balance is not None else None,
        total_return_pct=str(backtest.total_return) if backtest.total_return is not None else None,
        sharpe_ratio=str(backtest.sharpe_ratio) if backtest.sharpe_ratio is not None else None,
        max_drawdown_pct=str(backtest.max_drawdown) if backtest.max_drawdown is not None else None,
        win_rate=str(backtest.win_rate) if backtest.win_rate is not None else None,
        total_trades=backtest.total_trades,
        error_message=backtest.error_message,
        created_at=backtest.created_at,
        completed_at=backtest.completed_at,
        trade_log=[BacktestFillResponse(**fill) for fill in results.get("trade_log", [])],
        equity_curve=[BacktestEquityPointResponse(**point) for point in results.get("equity_curve", [])],
    )
