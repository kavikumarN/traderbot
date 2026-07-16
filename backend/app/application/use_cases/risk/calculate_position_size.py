"""Position-size calculator: a read-only preview of what
`RiskEngine.suggest_position_size` would recommend for a hypothetical
trade, using the user's active exchange account (if one exists yet) for
its equity figure. Places nothing — a caller that likes the numbers still
places the actual entry/stop orders itself via `TradingService`."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.risk_engine import RiskEngine
from app.domain.exchange.enums import OrderSide
from app.domain.trading.entities import ExchangeAccount


@dataclass(frozen=True, slots=True)
class CalculatePositionSizeCommand:
    user_id: uuid.UUID
    side: OrderSide
    entry_price: Decimal
    stop_loss_price: Decimal | None = None
    stop_loss_pct: Decimal | None = None
    risk_per_trade_pct: Decimal | None = None
    reward_risk_ratio: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    quantity: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    equity: Decimal


class CalculatePositionSizeUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, risk_engine: RiskEngine) -> None:
        self._uow_factory = uow_factory
        self._risk_engine = risk_engine

    async def execute(self, command: CalculatePositionSizeCommand) -> PositionSizeResult:
        async with self._uow_factory() as uow:
            account = await self._active_account(uow, command.user_id)
            equity = await self._risk_engine.compute_equity(uow, account) if account is not None else Decimal(0)
            quantity, stop_loss_price, take_profit_price = await self._risk_engine.suggest_position_size(
                uow,
                account=account,
                side=command.side,
                entry_price=command.entry_price,
                stop_loss_price=command.stop_loss_price,
                stop_loss_pct=command.stop_loss_pct,
                risk_per_trade_pct=command.risk_per_trade_pct,
                reward_risk_ratio=command.reward_risk_ratio,
            )
        return PositionSizeResult(
            quantity=quantity, stop_loss_price=stop_loss_price, take_profit_price=take_profit_price, equity=equity
        )

    async def _active_account(self, uow: UnitOfWork, user_id: uuid.UUID) -> ExchangeAccount | None:
        for account in await uow.exchange_accounts.list_for_user(user_id):
            if account.is_active:
                return account
        return None
