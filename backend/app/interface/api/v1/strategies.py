"""Strategy registration, lifecycle control, and signal history — the
Strategy Engine's (Phase 7) HTTP surface.

Route order matters here: `/strategies/types` is registered before
`/strategies/{strategy_id}` so "types" is never parsed as a strategy id.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.application.use_cases.backtesting.get_backtest import GetBacktestUseCase
from app.application.use_cases.backtesting.list_backtests import ListBacktestsUseCase
from app.application.use_cases.backtesting.run_backtest import RunBacktestCommand, RunBacktestUseCase
from app.application.use_cases.strategies.analyze_patterns import AnalyzePatternsCommand, AnalyzePatternsUseCase
from app.application.use_cases.strategies.create_strategy import (
    CreateStrategyCommand,
    CreateStrategyUseCase,
)
from app.application.use_cases.strategies.get_strategy import GetStrategyUseCase
from app.application.use_cases.strategies.list_signals import ListSignalsUseCase
from app.application.use_cases.strategies.list_strategies import ListStrategiesUseCase
from app.application.use_cases.strategies.update_strategy_status import (
    UpdateStrategyStatusCommand,
    UpdateStrategyStatusUseCase,
)
from app.domain.entities.user import User
from app.domain.strategy.plugin_manager import PluginManager
from app.interface.api.backtest_mappers import backtest_to_response
from app.interface.api.deps import (
    get_analyze_patterns_use_case,
    get_create_strategy_use_case,
    get_current_user,
    get_get_backtest_use_case,
    get_get_strategy_use_case,
    get_list_backtests_use_case,
    get_list_signals_use_case,
    get_list_strategies_use_case,
    get_plugin_manager,
    get_run_backtest_use_case,
    get_update_strategy_status_use_case,
    require_permission,
)
from app.interface.api.pattern_analysis_mappers import analyze_patterns_output_to_response
from app.interface.api.schemas.backtest import BacktestResponse, RunBacktestRequest
from app.interface.api.schemas.pattern_analysis import AnalyzePatternsRequest, PatternAnalysisResponse
from app.interface.api.schemas.strategy import (
    CreateStrategyRequest,
    SignalResponse,
    StrategyResponse,
    StrategyTypeResponse,
    UpdateStrategyStatusRequest,
)
from app.interface.api.strategy_mappers import signal_to_response, strategy_to_response

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("strategies:write"))],
    summary="Register a new strategy in DRAFT status",
)
async def create_strategy(
    body: CreateStrategyRequest,
    user: User = Depends(get_current_user),
    use_case: CreateStrategyUseCase = Depends(get_create_strategy_use_case),
) -> StrategyResponse:
    strategy = await use_case.execute(
        CreateStrategyCommand(
            user_id=user.id,
            name=body.name,
            description=body.description,
            symbol=body.symbol,
            strategy_type=body.strategy_type,
            parameters=body.parameters,
        )
    )
    return strategy_to_response(strategy)


@router.get(
    "",
    response_model=list[StrategyResponse],
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="List the current user's strategies",
)
async def list_strategies(
    user: User = Depends(get_current_user),
    use_case: ListStrategiesUseCase = Depends(get_list_strategies_use_case),
) -> list[StrategyResponse]:
    strategies = await use_case.execute(user_id=user.id)
    return [strategy_to_response(strategy) for strategy in strategies]


@router.get(
    "/types",
    response_model=list[StrategyTypeResponse],
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="List available strategy plugin types",
)
async def list_strategy_types(
    plugin_manager: PluginManager = Depends(get_plugin_manager),
) -> list[StrategyTypeResponse]:
    return [StrategyTypeResponse(strategy_type=t) for t in plugin_manager.list_available()]


@router.post(
    "/ai-builder/analyze",
    response_model=PatternAnalysisResponse,
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="AI Strategy Builder: detect candlestick/chart patterns across intervals and suggest a strategy",
)
async def analyze_patterns(
    body: AnalyzePatternsRequest,
    use_case: AnalyzePatternsUseCase = Depends(get_analyze_patterns_use_case),
) -> PatternAnalysisResponse:
    output = await use_case.execute(AnalyzePatternsCommand(symbol=body.symbol, intervals=body.intervals))
    return analyze_patterns_output_to_response(output)


@router.get(
    "/{strategy_id}",
    response_model=StrategyResponse,
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="Get a strategy",
)
async def get_strategy(
    strategy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    use_case: GetStrategyUseCase = Depends(get_get_strategy_use_case),
) -> StrategyResponse:
    strategy = await use_case.execute(user_id=user.id, strategy_id=strategy_id)
    return strategy_to_response(strategy)


@router.post(
    "/{strategy_id}/status",
    response_model=StrategyResponse,
    dependencies=[Depends(require_permission("strategies:write"))],
    summary="Transition a strategy's lifecycle status",
)
async def update_strategy_status(
    strategy_id: uuid.UUID,
    body: UpdateStrategyStatusRequest,
    user: User = Depends(get_current_user),
    use_case: UpdateStrategyStatusUseCase = Depends(get_update_strategy_status_use_case),
) -> StrategyResponse:
    strategy = await use_case.execute(
        UpdateStrategyStatusCommand(strategy_id=strategy_id, user_id=user.id, action=body.action)
    )
    return strategy_to_response(strategy)


@router.get(
    "/{strategy_id}/signals",
    response_model=list[SignalResponse],
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="List signals generated by a strategy",
)
async def list_signals(
    strategy_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user),
    use_case: ListSignalsUseCase = Depends(get_list_signals_use_case),
) -> list[SignalResponse]:
    signals = await use_case.execute(user_id=user.id, strategy_id=strategy_id, limit=limit, offset=offset)
    return [signal_to_response(signal) for signal in signals]


@router.post(
    "/{strategy_id}/backtests",
    response_model=BacktestResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("strategies:write"))],
    summary="Run a backtest: replay historical candles through this strategy's plugin and simulate fills",
)
async def run_backtest(
    strategy_id: uuid.UUID,
    body: RunBacktestRequest,
    user: User = Depends(get_current_user),
    use_case: RunBacktestUseCase = Depends(get_run_backtest_use_case),
) -> BacktestResponse:
    backtest = await use_case.execute(
        RunBacktestCommand(
            user_id=user.id,
            strategy_id=strategy_id,
            period_start=body.period_start,
            period_end=body.period_end,
            interval=body.interval,
            initial_balance=body.initial_balance,
            commission_rate=body.commission_rate,
            slippage_bps=body.slippage_bps,
        )
    )
    return backtest_to_response(backtest)


@router.get(
    "/{strategy_id}/backtests",
    response_model=list[BacktestResponse],
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="List backtests run against this strategy",
)
async def list_backtests(
    strategy_id: uuid.UUID,
    user: User = Depends(get_current_user),
    use_case: ListBacktestsUseCase = Depends(get_list_backtests_use_case),
) -> list[BacktestResponse]:
    backtests = await use_case.execute(user_id=user.id, strategy_id=strategy_id)
    return [backtest_to_response(backtest) for backtest in backtests]


@router.get(
    "/{strategy_id}/backtests/{backtest_id}",
    response_model=BacktestResponse,
    dependencies=[Depends(require_permission("strategies:read"))],
    summary="Get a backtest's full results (trade log, equity curve, summary stats)",
)
async def get_backtest(
    strategy_id: uuid.UUID,
    backtest_id: uuid.UUID,
    user: User = Depends(get_current_user),
    use_case: GetBacktestUseCase = Depends(get_get_backtest_use_case),
) -> BacktestResponse:
    backtest = await use_case.execute(user_id=user.id, strategy_id=strategy_id, backtest_id=backtest_id)
    return backtest_to_response(backtest)
