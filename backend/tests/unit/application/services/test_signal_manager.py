from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.execution_service import ExecutionService
from app.application.services.order_service import OrderService
from app.application.services.risk_engine import RiskEngine
from app.application.services.signal_manager import SignalManager
from app.application.services.trading_service import TradingService
from app.domain.exchange.enums import OrderSide, OrderStatus, OrderType
from app.domain.exchange.exceptions import InsufficientBalanceError as ExchangeInsufficientBalanceError
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.risk.entities import RiskRule
from app.domain.risk.enums import RiskRuleType
from app.domain.strategy.enums import SignalStatus, StrategyStatus
from app.domain.strategy.plugin import SignalProposal
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.unit.application.strategies.helpers import make_strategy


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


def make_signal_manager(uow_factory, **kwargs: object) -> tuple[SignalManager, FakeExchangeClient]:
    exchange = FakeExchangeClient()
    trading_service = TradingService(
        uow_factory, ExecutionService(), OrderService(), RiskEngine(), trading_mode="paper"
    )
    manager = SignalManager(uow_factory, trading_service, **kwargs)  # type: ignore[arg-type]
    return manager, exchange


@pytest.mark.asyncio
async def test_first_signal_on_tradeable_strategy_executes_and_is_consumed(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    exchange.place_order_result = make_exchange_order()
    exchange.balances = [AssetBalance(asset="USDT", free=Decimal("50000"), locked=Decimal(0))]
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    signal = await manager.submit(strategy, proposal, exchange=exchange)

    assert signal is not None
    assert signal.status == SignalStatus.CONSUMED
    stored = await uow.signals.get_by_id(signal.id)
    assert stored is not None
    assert stored.status == SignalStatus.CONSUMED
    assert len(exchange.placed_requests) == 1


@pytest.mark.asyncio
async def test_signal_on_non_tradeable_strategy_is_rejected_without_execution(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    strategy = make_strategy(status=StrategyStatus.DRAFT)
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    signal = await manager.submit(strategy, proposal, exchange=exchange)

    assert signal is not None
    assert signal.status == SignalStatus.REJECTED
    assert signal.rejection_reason is not None
    assert exchange.placed_requests == []


@pytest.mark.asyncio
async def test_duplicate_same_side_signal_within_cooldown_is_deduped(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    exchange.place_order_result = make_exchange_order()
    exchange.balances = [AssetBalance(asset="USDT", free=Decimal("50000"), locked=Decimal(0))]
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    first = await manager.submit(strategy, proposal, exchange=exchange)
    second = await manager.submit(strategy, proposal, exchange=exchange)

    assert first is not None
    assert second is None
    signals = await uow.signals.list_for_strategy(strategy.id)
    assert len(signals) == 1


@pytest.mark.asyncio
async def test_opposite_side_signal_within_cooldown_is_not_deduped(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    exchange.place_order_result = make_exchange_order()
    exchange.balances = [
        AssetBalance(asset="USDT", free=Decimal("50000"), locked=Decimal(0)),
        AssetBalance(asset="BTC", free=Decimal("10"), locked=Decimal(0)),
    ]
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    buy = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))
    sell = SignalProposal(side=OrderSide.SELL, quantity=Decimal("1"))

    first = await manager.submit(strategy, buy, exchange=exchange)
    second = await manager.submit(strategy, sell, exchange=exchange)

    assert first is not None
    assert second is not None
    signals = await uow.signals.list_for_strategy(strategy.id)
    assert len(signals) == 2


@pytest.mark.asyncio
async def test_order_rejection_from_exchange_marks_signal_rejected_with_reason(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    exchange.place_order_result = ExchangeInsufficientBalanceError("Insufficient USDT")
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    signal = await manager.submit(strategy, proposal, exchange=exchange)

    assert signal is not None
    assert signal.status == SignalStatus.REJECTED
    assert signal.rejection_reason == f"Insufficient {strategy.symbol} balance"
    stored = await uow.signals.get_by_id(signal.id)
    assert stored is not None
    assert stored.status == SignalStatus.REJECTED


@pytest.mark.asyncio
async def test_signal_rejected_by_risk_engine_marks_signal_rejected_with_reason(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    exchange.place_order_result = make_exchange_order()
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    await uow.risk_rules.add(
        RiskRule(
            id=uuid.uuid4(),
            user_id=strategy.user_id,
            rule_type=RiskRuleType.SYMBOL_WHITELIST,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            threshold=None,
            config={"symbols": ["ETHUSDT"]},
        )
    )
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    signal = await manager.submit(strategy, proposal, exchange=exchange)

    assert signal is not None
    assert signal.status == SignalStatus.REJECTED
    assert signal.rejection_reason is not None
    assert exchange.placed_requests == []


@pytest.mark.asyncio
async def test_auto_execute_false_leaves_signal_approved_without_executing(uow, uow_factory) -> None:
    manager, exchange = make_signal_manager(uow_factory)
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    proposal = SignalProposal(side=OrderSide.BUY, quantity=Decimal("1"))

    signal = await manager.submit(strategy, proposal, exchange=exchange, auto_execute=False)

    assert signal is not None
    assert signal.status == SignalStatus.APPROVED
    assert exchange.placed_requests == []
