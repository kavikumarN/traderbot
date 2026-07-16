"""Portfolio Service: the read/aggregation layer over the trading engine's
own tables (`wallets`, `positions`, `trade_history` — Phase 4/6). No new
ledger, no new ingestion — every number here is derived from data
`TradingService` already wrote on each fill.

Mirrors `RiskEngine`'s shape (a stateless engine taking a `UnitOfWork` per
call rather than owning one), including its `compute_equity` precedent —
except this one marks positions to market using a live ticker price where
`RiskEngine.compute_equity` deliberately uses avg-cost notional (it has no
price-feed dependency by design; a portfolio PnL view is the whole reason
to take that dependency here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.domain.portfolio.analytics import (
    EquityPoint,
    MonthlyReturn,
    build_equity_curve,
    bucket_monthly_returns,
    compute_current_drawdown,
    compute_max_drawdown,
    compute_sharpe_ratio,
)
from app.domain.trading.entities import ExchangeAccount, Position, Trade, Wallet

DEFAULT_QUOTE_ASSET = "USDT"


@dataclass(frozen=True, slots=True)
class PositionView:
    position: Position
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal


@dataclass(frozen=True, slots=True)
class PortfolioSummary:
    cash: Decimal
    positions_value: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    roi_pct: Decimal | None
    fees_by_asset: dict[str, Decimal]
    open_position_count: int
    total_trade_count: int


@dataclass(frozen=True, slots=True)
class PerformanceResult:
    points: list[EquityPoint] = field(default_factory=list)
    monthly_returns: list[MonthlyReturn] = field(default_factory=list)
    sharpe_ratio: Decimal | None = None
    max_drawdown_pct: Decimal = Decimal(0)
    current_drawdown_pct: Decimal = Decimal(0)
    starting_equity: Decimal = Decimal(0)
    current_equity: Decimal = Decimal(0)


class PortfolioService:
    def __init__(self, *, quote_asset: str = DEFAULT_QUOTE_ASSET) -> None:
        self._quote_asset = quote_asset.upper()

    # --- account resolution ---------------------------------------------------------------

    async def active_account(self, uow: UnitOfWork, user_id: uuid.UUID) -> ExchangeAccount | None:
        for account in await uow.exchange_accounts.list_for_user(user_id):
            if account.is_active:
                return account
        return None

    # --- equity -----------------------------------------------------------------------------

    async def compute_equity(
        self, uow: UnitOfWork, account: ExchangeAccount, market_data: IMarketDataReader
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Returns `(cash, positions_value, unrealized_pnl)`, each marked
        to market using the current ticker price. A symbol whose ticker
        fetch fails falls back to its stored `avg_entry_price` (zero
        unrealized pnl for that one symbol) rather than failing the whole
        read — a stale/unavailable price shouldn't 500 the portfolio page.
        """

        wallets = await uow.wallets.list_for_account(account.id)
        cash = sum((w.total for w in wallets if w.asset.upper() == self._quote_asset), Decimal(0))

        positions = await uow.positions.list_open_for_account(account.id)
        positions_value = Decimal(0)
        unrealized_pnl = Decimal(0)
        for position in positions:
            current_price = await self._current_price(market_data, position)
            positions_value += position.quantity * current_price
            unrealized_pnl += (current_price - position.avg_entry_price) * position.quantity

        return cash, positions_value, unrealized_pnl

    async def _current_price(self, market_data: IMarketDataReader, position: Position) -> Decimal:
        try:
            ticker = await market_data.get_ticker(position.symbol)
        except Exception:  # noqa: BLE001 - a single bad symbol shouldn't fail the whole portfolio read
            return position.avg_entry_price
        return ticker.last_price

    # --- summary ------------------------------------------------------------------------------

    async def get_summary(
        self, uow: UnitOfWork, account: ExchangeAccount, market_data: IMarketDataReader
    ) -> PortfolioSummary:
        cash, positions_value, unrealized_pnl = await self.compute_equity(uow, account, market_data)
        equity = cash + positions_value

        all_positions = await uow.positions.list_for_account(account.id)
        realized_pnl = sum((p.realized_pnl for p in all_positions), Decimal(0))
        open_position_count = sum(1 for p in all_positions if not p.is_closed)

        all_trades = await uow.trades.list_all_for_account(account.id)
        fees_by_asset: dict[str, Decimal] = {}
        for trade in all_trades:
            asset = (trade.commission_asset or self._quote_asset).upper()
            fees_by_asset[asset] = fees_by_asset.get(asset, Decimal(0)) + trade.commission

        total_pnl = realized_pnl + unrealized_pnl
        equity_curve = build_equity_curve(all_trades, current_equity=equity, as_of=datetime.now(UTC).date())
        starting_equity = equity_curve[0].equity if equity_curve else None
        roi_pct = (equity - starting_equity) / starting_equity if starting_equity else None

        return PortfolioSummary(
            cash=cash,
            positions_value=positions_value,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            roi_pct=roi_pct,
            fees_by_asset=fees_by_asset,
            open_position_count=open_position_count,
            total_trade_count=len(all_trades),
        )

    # --- positions ----------------------------------------------------------------------------

    async def get_positions(
        self, uow: UnitOfWork, account: ExchangeAccount, market_data: IMarketDataReader
    ) -> list[PositionView]:
        positions = await uow.positions.list_open_for_account(account.id)
        views: list[PositionView] = []
        for position in positions:
            current_price = await self._current_price(market_data, position)
            market_value = position.quantity * current_price
            unrealized_pnl = (current_price - position.avg_entry_price) * position.quantity
            cost_basis = position.avg_entry_price * abs(position.quantity)
            unrealized_pnl_pct = unrealized_pnl / cost_basis if cost_basis != 0 else Decimal(0)
            views.append(
                PositionView(
                    position=position,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                )
            )
        return views

    # --- wallets / trade history ---------------------------------------------------------------

    async def get_wallets(self, uow: UnitOfWork, account: ExchangeAccount) -> list[Wallet]:
        return await uow.wallets.list_for_account(account.id)

    async def get_trade_history(
        self, uow: UnitOfWork, account: ExchangeAccount, *, limit: int, offset: int
    ) -> list[Trade]:
        return await uow.trades.list_for_account(account.id, limit=limit, offset=offset)

    # --- performance ----------------------------------------------------------------------------

    async def get_performance(
        self, uow: UnitOfWork, account: ExchangeAccount, market_data: IMarketDataReader
    ) -> PerformanceResult:
        cash, positions_value, _unrealized_pnl = await self.compute_equity(uow, account, market_data)
        current_equity = cash + positions_value

        all_trades = await uow.trades.list_all_for_account(account.id)
        points = build_equity_curve(all_trades, current_equity=current_equity, as_of=datetime.now(UTC).date())
        if not points:
            return PerformanceResult(current_equity=current_equity)

        return PerformanceResult(
            points=points,
            monthly_returns=bucket_monthly_returns(points),
            sharpe_ratio=compute_sharpe_ratio(points),
            max_drawdown_pct=compute_max_drawdown(points),
            current_drawdown_pct=compute_current_drawdown(points),
            starting_equity=points[0].equity,
            current_equity=current_equity,
        )
