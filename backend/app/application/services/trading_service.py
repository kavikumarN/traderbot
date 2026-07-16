"""Trading Service: the trading engine's single application-layer entry
point — what the API layer calls to place, cancel, track, and audit orders.

Orchestrates `OrderService` (order-repository lifecycle) and
`ExecutionService` (exchange I/O) inside one `UnitOfWork` transaction per
operation, and is where the cross-aggregate bookkeeping a single order
placement triggers actually happens: recording the resulting `Trade` on a
fill, updating the platform's own `Position` (weighted-average-cost), and
resyncing `Wallet` balances from the exchange — plus an `AuditLog` entry for
every state-changing action, satisfying this platform's append-only audit
trail requirement.

Exchange-account resolution is intentionally simple: this phase doesn't
build a "connect your exchange account" flow (linking real API keys is a
distinct, security-sensitive feature), so each user gets one
lazily-provisioned default account per trading mode ("PAPER" or "BINANCE").
Multi-account support can layer on top later without changing this
orchestration.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.execution_service import ExecutionService
from app.application.services.order_service import OrderService
from app.application.services.risk_engine import RiskEngine
from app.domain.audit.entities import AuditLog
from app.domain.exceptions import EntityNotFoundError
from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.risk.exceptions import (
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
    RiskLimitExceededError,
)
from app.domain.trading.entities import ExchangeAccount, Order, Position, Trade, Wallet
from app.domain.trading.enums import AccountStatus, PlatformOrderStatus
from app.domain.trading.exceptions import (
    AccountNotActiveError,
    InsufficientBalanceError,
    OrderRejectedError,
)

_RISK_REJECTION_EXCEPTIONS = (RiskLimitExceededError, CircuitBreakerTrippedError, EmergencyStopActiveError)

TradingMode = Literal["paper", "live"]

_PAPER_EXCHANGE_LABEL = "PAPER"
_LIVE_EXCHANGE_LABEL = "BINANCE"


class TradingService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        execution_service: ExecutionService,
        order_service: OrderService,
        risk_engine: RiskEngine,
        *,
        trading_mode: TradingMode = "paper",
    ) -> None:
        self._uow_factory = uow_factory
        self._execution = execution_service
        self._orders = order_service
        self._risk = risk_engine
        self._trading_mode = trading_mode

    # --- placing orders -------------------------------------------------------------------

    async def place_market_order(
        self,
        *,
        user_id: uuid.UUID,
        exchange: ExchangeClient,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        strategy_id: uuid.UUID | None = None,
        signal_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        return await self._place_order(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            strategy_id=strategy_id,
            signal_id=signal_id,
            client_order_id=client_order_id,
        )

    async def place_limit_order(
        self,
        *,
        user_id: uuid.UUID,
        exchange: ExchangeClient,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
        time_in_force: TimeInForce = TimeInForce.GTC,
        strategy_id: uuid.UUID | None = None,
        signal_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        return await self._place_order(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            time_in_force=time_in_force,
            strategy_id=strategy_id,
            signal_id=signal_id,
            client_order_id=client_order_id,
        )

    async def place_stop_order(
        self,
        *,
        user_id: uuid.UUID,
        exchange: ExchangeClient,
        symbol: str,
        side: OrderSide,
        quantity: Decimal,
        stop_price: Decimal,
        limit_price: Decimal | None = None,
        strategy_id: uuid.UUID | None = None,
        signal_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        # A stop order with no limit price triggers into a market order
        # (STOP_LOSS); with one, it triggers into a resting limit order
        # (STOP_LOSS_LIMIT) — same distinction Binance itself makes.
        order_type = OrderType.STOP_LOSS_LIMIT if limit_price is not None else OrderType.STOP_LOSS
        return await self._place_order(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=limit_price,
            stop_price=stop_price,
            time_in_force=TimeInForce.GTC if limit_price is not None else None,
            strategy_id=strategy_id,
            signal_id=signal_id,
            client_order_id=client_order_id,
        )

    async def _place_order(
        self,
        *,
        user_id: uuid.UUID,
        exchange: ExchangeClient,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
        stop_price: Decimal | None = None,
        time_in_force: TimeInForce | None = None,
        strategy_id: uuid.UUID | None = None,
        signal_id: uuid.UUID | None = None,
        client_order_id: str | None = None,
    ) -> Order:
        async with self._uow_factory() as uow:
            account = await self._resolve_account(uow, user_id)
            order = self._orders.build_order(
                exchange_account_id=account.id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                time_in_force=time_in_force,
                strategy_id=strategy_id,
                signal_id=signal_id,
                client_order_id=client_order_id,
            )
            await uow.orders.add(order)

            # Every order — whether placed directly through this API or
            # routed here from a strategy `Signal` via `SignalManager` — is
            # gated by the Risk Engine before it ever reaches
            # `ExecutionService`/the exchange. `PENDING_RISK` is exactly
            # this window: the order exists, but hasn't earned the right to
            # be submitted yet.
            try:
                await self._risk.evaluate(uow, order=order, account=account, strategy_id=strategy_id)
            except _RISK_REJECTION_EXCEPTIONS as exc:
                await self._reject_order(uow, order, exc.message, user_id, event_type="order.risk_rejected")
                raise

            order.status = PlatformOrderStatus.PENDING_SUBMIT
            await uow.orders.update(order)

            try:
                order = await self._execution.submit_order(order, exchange)
            except (OrderRejectedError, InsufficientBalanceError) as exc:
                await self._reject_order(uow, order, exc.message, user_id, event_type="order.rejected")
                raise

            await uow.orders.update(order)
            await self._record_fill(uow, exchange, order, previous_executed_quantity=Decimal(0))
            await self._audit(uow, "order.submitted", order, user_id)
            await uow.commit()
        return order

    async def _reject_order(
        self, uow: UnitOfWork, order: Order, reason: str, user_id: uuid.UUID, *, event_type: str
    ) -> None:
        order.status = PlatformOrderStatus.REJECTED
        order.rejection_reason = reason
        order.updated_at = datetime.now(UTC)
        await uow.orders.update(order)
        await self._audit(uow, event_type, order, user_id)
        await uow.commit()

    # --- cancelling / tracking -------------------------------------------------------------

    async def cancel_order(self, *, user_id: uuid.UUID, exchange: ExchangeClient, order_id: uuid.UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await self._orders.get_order(uow, order_id)
            await self._ensure_owned(uow, order, user_id)
            self._orders.ensure_cancelable(order)

            order = await self._execution.cancel_order(order, exchange)
            await uow.orders.update(order)
            await self._audit(uow, "order.cancelled", order, user_id)
            await uow.commit()
        return order

    async def sync_order(self, *, user_id: uuid.UUID, exchange: ExchangeClient, order_id: uuid.UUID) -> Order:
        """Re-fetches a resting order's status from the exchange — the
        polling counterpart to a live push feed, for order tracking on
        limit/stop orders that don't fill the instant they're placed."""

        async with self._uow_factory() as uow:
            order = await self._orders.get_order(uow, order_id)
            await self._ensure_owned(uow, order, user_id)
            if order.is_terminal:
                return order

            previous_executed_quantity = order.executed_quantity
            order = await self._execution.refresh_order(order, exchange)
            await uow.orders.update(order)
            await self._record_fill(uow, exchange, order, previous_executed_quantity=previous_executed_quantity)
            if order.executed_quantity > previous_executed_quantity:
                await self._audit(uow, "order.filled", order, user_id)
            await uow.commit()
        return order

    # --- reads ------------------------------------------------------------------------------

    async def get_order(self, *, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
        async with self._uow_factory() as uow:
            order = await self._orders.get_order(uow, order_id)
            await self._ensure_owned(uow, order, user_id)
            return order

    async def list_open_orders(self, *, user_id: uuid.UUID) -> list[Order]:
        async with self._uow_factory() as uow:
            account = await self._active_account(uow, user_id)
            if account is None:
                return []
            return await self._orders.list_open_orders(uow, account.id)

    async def list_order_history(self, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[Order]:
        async with self._uow_factory() as uow:
            account = await self._active_account(uow, user_id)
            if account is None:
                return []
            return await self._orders.list_order_history(uow, account.id, limit=limit, offset=offset)

    async def get_order_audit_log(self, *, user_id: uuid.UUID, order_id: uuid.UUID) -> list[AuditLog]:
        async with self._uow_factory() as uow:
            order = await self._orders.get_order(uow, order_id)
            await self._ensure_owned(uow, order, user_id)
            return await uow.audit_logs.list_for_entity("Order", order_id)

    # --- internals ----------------------------------------------------------------------------

    async def _resolve_account(self, uow: UnitOfWork, user_id: uuid.UUID) -> ExchangeAccount:
        exchange_label = _PAPER_EXCHANGE_LABEL if self._trading_mode == "paper" else _LIVE_EXCHANGE_LABEL
        for account in await uow.exchange_accounts.list_for_user(user_id):
            if account.exchange == exchange_label:
                if not account.is_active:
                    raise AccountNotActiveError(account.id)
                return account

        now = datetime.now(UTC)
        account = ExchangeAccount(
            id=uuid.uuid4(),
            user_id=user_id,
            exchange=exchange_label,
            label="default",
            api_key_ciphertext="",
            api_key_last_four="0000",
            is_testnet=self._trading_mode == "paper",
            status=AccountStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        await uow.exchange_accounts.add(account)
        return account

    async def _active_account(self, uow: UnitOfWork, user_id: uuid.UUID) -> ExchangeAccount | None:
        exchange_label = _PAPER_EXCHANGE_LABEL if self._trading_mode == "paper" else _LIVE_EXCHANGE_LABEL
        for account in await uow.exchange_accounts.list_for_user(user_id):
            if account.exchange == exchange_label and account.is_active:
                return account
        return None

    async def _ensure_owned(self, uow: UnitOfWork, order: Order, user_id: uuid.UUID) -> None:
        account = await uow.exchange_accounts.get_by_id(order.exchange_account_id)
        if account is None or account.user_id != user_id:
            # Deliberately the same 404 a nonexistent order id would raise —
            # an order id that exists but belongs to someone else shouldn't
            # be distinguishable from one that doesn't exist at all.
            raise EntityNotFoundError("Order", order.id)

    async def _record_fill(
        self, uow: UnitOfWork, exchange: ExchangeClient, order: Order, *, previous_executed_quantity: Decimal
    ) -> None:
        trade = self._execution.build_fill_trade(order, previous_executed_quantity)
        if trade is None:
            return
        await uow.trades.add(trade)
        realized_pnl_delta = await self._apply_fill_to_position(uow, order, trade)
        await self._sync_wallets(uow, exchange, order.exchange_account_id)

        # Feeds this fill's newly-realized pnl back into the Risk Engine's
        # daily-loss/drawdown/consecutive-loss counters — the other half of
        # the loop from the pre-trade gate in `_place_order`. A losing
        # streak can trip the circuit breaker here, before the next order
        # is even proposed.
        account = await uow.exchange_accounts.get_by_id(order.exchange_account_id)
        if account is not None:
            await self._risk.record_fill(uow, account=account, realized_pnl_delta=realized_pnl_delta)

    async def _apply_fill_to_position(self, uow: UnitOfWork, order: Order, trade: Trade) -> Decimal:
        position = await uow.positions.get(order.exchange_account_id, order.symbol)
        now = datetime.now(UTC)
        previous_realized_pnl = position.realized_pnl if position is not None else Decimal(0)

        if position is None:
            signed_quantity = trade.quantity if order.side == OrderSide.BUY else -trade.quantity
            position = Position(
                id=uuid.uuid4(),
                exchange_account_id=order.exchange_account_id,
                symbol=order.symbol,
                quantity=signed_quantity,
                avg_entry_price=trade.price,
                realized_pnl=Decimal(0),
                opened_at=now,
                updated_at=now,
            )
        else:
            position = _apply_fill_to_existing_position(position, order.side, trade, now)

        await uow.positions.upsert(position)
        return position.realized_pnl - previous_realized_pnl

    async def _sync_wallets(self, uow: UnitOfWork, exchange: ExchangeClient, exchange_account_id: uuid.UUID) -> None:
        now = datetime.now(UTC)
        for balance in await exchange.get_balances():
            existing = await uow.wallets.get(exchange_account_id, balance.asset)
            await uow.wallets.upsert(
                Wallet(
                    id=existing.id if existing else uuid.uuid4(),
                    exchange_account_id=exchange_account_id,
                    asset=balance.asset,
                    free=balance.free,
                    locked=balance.locked,
                    updated_at=now,
                )
            )

    async def _audit(self, uow: UnitOfWork, event_type: str, order: Order, user_id: uuid.UUID) -> None:
        await uow.audit_logs.add(
            AuditLog(
                id=uuid.uuid4(),
                event_type=event_type,
                entity_type="Order",
                entity_id=order.id,
                actor_user_id=user_id,
                occurred_at=datetime.now(UTC),
                payload=_order_audit_payload(order),
            )
        )


def _apply_fill_to_existing_position(position: Position, side: OrderSide, trade: Trade, now: datetime) -> Position:
    """Weighted-average-cost accounting: a fill in the same direction as the
    open position extends it (blending the entry price); a fill against it
    closes/reduces (realizing pnl at the trade price) and, if it overshoots,
    flips the position onto the new side at the trade's price."""

    signed_quantity = trade.quantity if side == OrderSide.BUY else -trade.quantity
    same_direction = position.quantity == 0 or (position.quantity > 0) == (signed_quantity > 0)
    new_quantity = position.quantity + signed_quantity

    if same_direction:
        total_cost = position.avg_entry_price * abs(position.quantity) + trade.price * trade.quantity
        avg_entry_price = total_cost / abs(new_quantity) if new_quantity != 0 else Decimal(0)
        realized_pnl = position.realized_pnl
    else:
        closing_quantity = min(abs(signed_quantity), abs(position.quantity))
        direction = Decimal(1) if position.quantity > 0 else Decimal(-1)
        realized_pnl = position.realized_pnl + direction * (trade.price - position.avg_entry_price) * closing_quantity
        flipped = (new_quantity > 0) != (position.quantity > 0) and new_quantity != 0
        avg_entry_price = trade.price if flipped else position.avg_entry_price

    return Position(
        id=position.id,
        exchange_account_id=position.exchange_account_id,
        symbol=position.symbol,
        quantity=new_quantity,
        avg_entry_price=avg_entry_price if new_quantity != 0 else Decimal(0),
        realized_pnl=realized_pnl,
        opened_at=position.opened_at,
        updated_at=now,
        closed_at=now if new_quantity == 0 else None,
    )


def _order_audit_payload(order: Order) -> dict[str, Any]:
    return {
        "symbol": order.symbol,
        "side": order.side.value,
        "type": order.type.value,
        "status": order.status.value,
        "quantity": str(order.quantity),
        "executed_quantity": str(order.executed_quantity),
        "cumulative_quote_quantity": str(order.cumulative_quote_quantity),
        "price": str(order.price) if order.price is not None else None,
        "stop_price": str(order.stop_price) if order.stop_price is not None else None,
        "exchange_order_id": order.exchange_order_id,
        "rejection_reason": order.rejection_reason,
    }
