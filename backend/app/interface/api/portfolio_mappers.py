"""Domain entity / service-result -> response schema mappers for the
portfolio API — pure functions, no logic beyond field copying/`str()`,
matching `app.interface.api.risk_mappers`."""

from __future__ import annotations

from app.application.services.portfolio_service import PortfolioSummary, PositionView
from app.domain.portfolio.analytics import EquityPoint, MonthlyReturn
from app.domain.trading.entities import Trade, Wallet
from app.interface.api.schemas.portfolio import (
    EquityPointResponse,
    MonthlyReturnResponse,
    PortfolioSummaryResponse,
    PositionResponse,
    TradeResponse,
    WalletResponse,
)


def wallet_to_response(wallet: Wallet) -> WalletResponse:
    return WalletResponse(
        id=wallet.id,
        asset=wallet.asset,
        free=str(wallet.free),
        locked=str(wallet.locked),
        total=str(wallet.total),
        updated_at=wallet.updated_at,
    )


def position_view_to_response(view: PositionView) -> PositionResponse:
    position = view.position
    return PositionResponse(
        id=position.id,
        symbol=position.symbol,
        quantity=str(position.quantity),
        avg_entry_price=str(position.avg_entry_price),
        current_price=str(view.current_price),
        market_value=str(view.market_value),
        unrealized_pnl=str(view.unrealized_pnl),
        unrealized_pnl_pct=str(view.unrealized_pnl_pct),
        realized_pnl=str(position.realized_pnl),
        opened_at=position.opened_at,
        updated_at=position.updated_at,
    )


def trade_to_response(trade: Trade) -> TradeResponse:
    return TradeResponse(
        id=trade.id,
        order_id=trade.order_id,
        symbol=trade.symbol,
        side=trade.side.value,
        price=str(trade.price),
        quantity=str(trade.quantity),
        quote_quantity=str(trade.quote_quantity),
        commission=str(trade.commission),
        commission_asset=trade.commission_asset,
        executed_at=trade.executed_at,
    )


def summary_to_response(summary: PortfolioSummary) -> PortfolioSummaryResponse:
    return PortfolioSummaryResponse(
        cash=str(summary.cash),
        positions_value=str(summary.positions_value),
        equity=str(summary.equity),
        realized_pnl=str(summary.realized_pnl),
        unrealized_pnl=str(summary.unrealized_pnl),
        total_pnl=str(summary.total_pnl),
        roi_pct=str(summary.roi_pct) if summary.roi_pct is not None else None,
        fees_by_asset={asset: str(amount) for asset, amount in summary.fees_by_asset.items()},
        open_position_count=summary.open_position_count,
        total_trade_count=summary.total_trade_count,
    )


def equity_point_to_response(point: EquityPoint) -> EquityPointResponse:
    return EquityPointResponse(
        date=point.date,
        equity=str(point.equity),
        realized_pnl_cum=str(point.realized_pnl_cum),
        fees_cum=str(point.fees_cum),
    )


def monthly_return_to_response(monthly_return: MonthlyReturn) -> MonthlyReturnResponse:
    return MonthlyReturnResponse(
        month=monthly_return.month,
        return_pct=str(monthly_return.return_pct),
        pnl=str(monthly_return.pnl),
    )
