"""Portfolio management — the read/aggregation HTTP surface over the
trading engine's own tables (Phase 9). Every route here is a query: wallet
balances, positions marked to market, trade history, a PnL/ROI/fee
summary, and derived performance analytics (equity curve, monthly
returns, Sharpe ratio, drawdown). Nothing here writes anything —
`TradingService` (`/trading/orders/*`) already owns every write path this
data comes from.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.application.use_cases.portfolio.get_performance import GetPerformanceUseCase
from app.application.use_cases.portfolio.get_summary import GetPortfolioSummaryUseCase
from app.application.use_cases.portfolio.list_positions import ListPositionsUseCase
from app.application.use_cases.portfolio.list_trade_history import ListTradeHistoryUseCase
from app.application.use_cases.portfolio.list_wallets import ListWalletsUseCase
from app.domain.entities.user import User
from app.interface.api.deps import (
    get_current_user,
    get_get_performance_use_case,
    get_get_portfolio_summary_use_case,
    get_list_positions_use_case,
    get_list_trade_history_use_case,
    get_list_wallets_use_case,
    require_permission,
)
from app.interface.api.portfolio_mappers import (
    equity_point_to_response,
    monthly_return_to_response,
    position_view_to_response,
    summary_to_response,
    trade_to_response,
    wallet_to_response,
)
from app.interface.api.schemas.portfolio import (
    PerformanceResponse,
    PortfolioSummaryResponse,
    PositionResponse,
    TradeHistoryResponse,
    WalletResponse,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get(
    "/summary",
    response_model=PortfolioSummaryResponse,
    dependencies=[Depends(require_permission("portfolio:read"))],
    summary="Portfolio headline numbers: cash, equity, realized/unrealized pnl, ROI, fees",
)
async def get_summary(
    user: User = Depends(get_current_user),
    use_case: GetPortfolioSummaryUseCase = Depends(get_get_portfolio_summary_use_case),
) -> PortfolioSummaryResponse:
    summary = await use_case.execute(user_id=user.id)
    return summary_to_response(summary)


@router.get(
    "/wallets",
    response_model=list[WalletResponse],
    dependencies=[Depends(require_permission("portfolio:read"))],
    summary="Wallet balances (free/locked) per asset",
)
async def list_wallets(
    user: User = Depends(get_current_user),
    use_case: ListWalletsUseCase = Depends(get_list_wallets_use_case),
) -> list[WalletResponse]:
    wallets = await use_case.execute(user_id=user.id)
    return [wallet_to_response(wallet) for wallet in wallets]


@router.get(
    "/positions",
    response_model=list[PositionResponse],
    dependencies=[Depends(require_permission("portfolio:read"))],
    summary="Open positions, marked to market",
)
async def list_positions(
    user: User = Depends(get_current_user),
    use_case: ListPositionsUseCase = Depends(get_list_positions_use_case),
) -> list[PositionResponse]:
    positions = await use_case.execute(user_id=user.id)
    return [position_view_to_response(view) for view in positions]


@router.get(
    "/trades",
    response_model=TradeHistoryResponse,
    dependencies=[Depends(require_permission("portfolio:read"))],
    summary="Trade (fill) history",
)
async def list_trade_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: User = Depends(get_current_user),
    use_case: ListTradeHistoryUseCase = Depends(get_list_trade_history_use_case),
) -> TradeHistoryResponse:
    trades = await use_case.execute(user_id=user.id, limit=limit, offset=offset)
    return TradeHistoryResponse(items=[trade_to_response(trade) for trade in trades], offset=offset, limit=limit)


@router.get(
    "/performance",
    response_model=PerformanceResponse,
    dependencies=[Depends(require_permission("portfolio:read"))],
    summary="Equity curve, monthly returns, Sharpe ratio, and drawdown",
)
async def get_performance(
    user: User = Depends(get_current_user),
    use_case: GetPerformanceUseCase = Depends(get_get_performance_use_case),
) -> PerformanceResponse:
    result = await use_case.execute(user_id=user.id)
    return PerformanceResponse(
        points=[equity_point_to_response(point) for point in result.points],
        monthly_returns=[monthly_return_to_response(item) for item in result.monthly_returns],
        sharpe_ratio=str(result.sharpe_ratio) if result.sharpe_ratio is not None else None,
        max_drawdown_pct=str(result.max_drawdown_pct),
        current_drawdown_pct=str(result.current_drawdown_pct),
        starting_equity=str(result.starting_equity),
        current_equity=str(result.current_equity),
    )
