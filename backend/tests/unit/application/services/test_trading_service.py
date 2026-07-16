from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.execution_service import ExecutionService
from app.application.services.order_service import OrderService
from app.application.services.risk_engine import RiskEngine
from app.application.services.trading_service import TradingService
from app.domain.exceptions import EntityNotFoundError
from app.domain.exchange.enums import OrderSide, OrderStatus, OrderType
from app.domain.exchange.exceptions import InsufficientBalanceError as ExchangeInsufficientBalanceError
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.risk.entities import RiskRule
from app.domain.risk.enums import RiskRuleType
from app.domain.risk.exceptions import RiskLimitExceededError
from app.domain.trading.enums import PlatformOrderStatus
from app.domain.trading.exceptions import InsufficientBalanceError, OrderNotCancelableError
from tests.fakes.fake_exchange_client import FakeExchangeClient


def make_exchange_order(**overrides: object) -> ExchangeOrder:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        exchange_order_id=1001,
        client_order_id="tb-test",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        time_in_force=None,
        price=Decimal("50000"),
        original_quantity=Decimal("1"),
        executed_quantity=Decimal("1"),
        cumulative_quote_quantity=Decimal("50000"),
        created_at=now,
        updated_at=now,
        stop_price=None,
    )
    defaults.update(overrides)
    return ExchangeOrder(**defaults)  # type: ignore[arg-type]


def make_service(uow_factory) -> tuple[TradingService, FakeExchangeClient]:
    exchange = FakeExchangeClient()
    service = TradingService(uow_factory, ExecutionService(), OrderService(), RiskEngine(), trading_mode="paper")
    return service, exchange


@pytest.mark.asyncio
async def test_place_market_order_fills_immediately_and_records_fill(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = make_exchange_order()
    exchange.balances = [AssetBalance(asset="USDT", free=Decimal("50000"), locked=Decimal(0))]
    user_id = uuid.uuid4()

    order = await service.place_market_order(
        user_id=user_id, exchange=exchange, symbol="BTCUSDT", side=OrderSide.BUY, quantity=Decimal("1")
    )

    assert order.status == PlatformOrderStatus.FILLED
    assert order.executed_quantity == Decimal("1")
    assert uow.committed

    stored = await uow.orders.get_by_id(order.id)
    assert stored is not None
    assert stored.status == PlatformOrderStatus.FILLED

    trades = await uow.trades.list_for_order(order.id)
    assert len(trades) == 1
    assert trades[0].quantity == Decimal("1")

    position = await uow.positions.get(order.exchange_account_id, "BTCUSDT")
    assert position is not None
    assert position.quantity == Decimal("1")

    wallet = await uow.wallets.get(order.exchange_account_id, "USDT")
    assert wallet is not None
    assert wallet.free == Decimal("50000")

    audit_entries = await uow.audit_logs.list_for_entity("Order", order.id)
    assert any(entry.event_type == "order.submitted" for entry in audit_entries)


@pytest.mark.asyncio
async def test_place_limit_order_rests_without_recording_a_fill(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = make_exchange_order(
        type=OrderType.LIMIT, status=OrderStatus.NEW, executed_quantity=Decimal(0), cumulative_quote_quantity=Decimal(0)
    )
    user_id = uuid.uuid4()

    order = await service.place_limit_order(
        user_id=user_id,
        exchange=exchange,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("40000"),
    )

    assert order.status == PlatformOrderStatus.SUBMITTED
    assert not order.is_terminal
    trades = await uow.trades.list_for_order(order.id)
    assert trades == []


@pytest.mark.asyncio
async def test_place_order_rejected_on_insufficient_balance_marks_order_rejected(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = ExchangeInsufficientBalanceError("Insufficient USDT")
    user_id = uuid.uuid4()

    with pytest.raises(InsufficientBalanceError):
        await service.place_market_order(
            user_id=user_id, exchange=exchange, symbol="BTCUSDT", side=OrderSide.BUY, quantity=Decimal("1")
        )

    orders = await uow.orders.list_for_account(
        (await uow.exchange_accounts.list_for_user(user_id))[0].id
    )
    assert len(orders) == 1
    assert orders[0].status == PlatformOrderStatus.REJECTED
    assert orders[0].rejection_reason == "Insufficient BTCUSDT balance"

    audit_entries = await uow.audit_logs.list_for_entity("Order", orders[0].id)
    assert any(entry.event_type == "order.rejected" for entry in audit_entries)


@pytest.mark.asyncio
async def test_cancel_order_updates_status(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = make_exchange_order(
        type=OrderType.LIMIT, status=OrderStatus.NEW, executed_quantity=Decimal(0), cumulative_quote_quantity=Decimal(0)
    )
    user_id = uuid.uuid4()
    order = await service.place_limit_order(
        user_id=user_id,
        exchange=exchange,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("40000"),
    )

    exchange.cancel_order_result = make_exchange_order(
        type=OrderType.LIMIT,
        status=OrderStatus.CANCELED,
        executed_quantity=Decimal(0),
        cumulative_quote_quantity=Decimal(0),
    )
    cancelled = await service.cancel_order(user_id=user_id, exchange=exchange, order_id=order.id)

    assert cancelled.status == PlatformOrderStatus.CANCELLED

    with pytest.raises(OrderNotCancelableError):
        await service.cancel_order(user_id=user_id, exchange=exchange, order_id=order.id)


@pytest.mark.asyncio
async def test_get_order_by_another_user_raises_not_found(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = make_exchange_order()
    owner_id = uuid.uuid4()
    order = await service.place_market_order(
        user_id=owner_id, exchange=exchange, symbol="BTCUSDT", side=OrderSide.BUY, quantity=Decimal("1")
    )

    with pytest.raises(EntityNotFoundError):
        await service.get_order(user_id=uuid.uuid4(), order_id=order.id)


@pytest.mark.asyncio
async def test_place_order_rejected_by_risk_engine_never_reaches_the_exchange(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    exchange.place_order_result = make_exchange_order()
    user_id = uuid.uuid4()
    await uow.risk_rules.add(
        RiskRule(
            id=uuid.uuid4(),
            user_id=user_id,
            rule_type=RiskRuleType.MAX_POSITION_NOTIONAL,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            threshold=Decimal("10000"),
        )
    )

    with pytest.raises(RiskLimitExceededError):
        await service.place_limit_order(
            user_id=user_id,
            exchange=exchange,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=Decimal("1"),
            price=Decimal("50000"),
        )

    assert exchange.placed_requests == []
    orders = await uow.orders.list_for_account((await uow.exchange_accounts.list_for_user(user_id))[0].id)
    assert len(orders) == 1
    assert orders[0].status == PlatformOrderStatus.REJECTED
    assert "10000" in orders[0].rejection_reason


@pytest.mark.asyncio
async def test_list_order_history_and_open_orders(uow, uow_factory) -> None:
    service, exchange = make_service(uow_factory)
    user_id = uuid.uuid4()

    exchange.place_order_result = make_exchange_order(exchange_order_id=1)
    filled = await service.place_market_order(
        user_id=user_id, exchange=exchange, symbol="BTCUSDT", side=OrderSide.BUY, quantity=Decimal("1")
    )

    exchange.place_order_result = make_exchange_order(
        exchange_order_id=2,
        type=OrderType.LIMIT,
        status=OrderStatus.NEW,
        executed_quantity=Decimal(0),
        cumulative_quote_quantity=Decimal(0),
    )
    resting = await service.place_limit_order(
        user_id=user_id,
        exchange=exchange,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        quantity=Decimal("1"),
        price=Decimal("40000"),
    )

    history = await service.list_order_history(user_id=user_id)
    assert {o.id for o in history} == {filled.id, resting.id}

    open_orders = await service.list_open_orders(user_id=user_id)
    assert {o.id for o in open_orders} == {resting.id}
