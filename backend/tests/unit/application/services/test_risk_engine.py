from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.services.risk_engine import RiskEngine
from app.domain.exchange.enums import OrderSide, OrderType
from app.domain.risk.entities import RiskRule, RiskState
from app.domain.risk.enums import CircuitBreakerState, RiskRuleType
from app.domain.risk.exceptions import (
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
    RiskLimitExceededError,
)
from app.domain.trading.entities import ExchangeAccount, Order, Position, Wallet
from app.domain.trading.enums import AccountStatus, PlatformOrderStatus

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def make_account(**overrides: object) -> ExchangeAccount:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        exchange="PAPER",
        label="default",
        api_key_ciphertext="",
        api_key_last_four="0000",
        is_testnet=True,
        status=AccountStatus.ACTIVE,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return ExchangeAccount(**defaults)  # type: ignore[arg-type]


def make_order(account: ExchangeAccount, **overrides: object) -> Order:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        exchange_account_id=account.id,
        symbol="BTCUSDT",
        side=OrderSide.BUY,
        type=OrderType.MARKET,
        status=PlatformOrderStatus.PENDING_RISK,
        quantity=Decimal("1"),
        executed_quantity=Decimal("0"),
        cumulative_quote_quantity=Decimal("0"),
        client_order_id=f"tb-{uuid.uuid4().hex}",
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return Order(**defaults)  # type: ignore[arg-type]


def make_rule(user_id: uuid.UUID, rule_type: RiskRuleType, threshold: Decimal | None, **overrides: object) -> RiskRule:
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        user_id=user_id,
        rule_type=rule_type,
        is_active=True,
        created_at=_NOW,
        updated_at=_NOW,
        strategy_id=None,
        threshold=threshold,
        config={},
    )
    defaults.update(overrides)
    return RiskRule(**defaults)  # type: ignore[arg-type]


async def test_evaluate_approves_when_no_rules_and_no_prior_state(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    order = make_order(account, price=Decimal("50000"))

    assessment = await engine.evaluate(uow, order=order, account=account)

    assert assessment.approved
    assert assessment.reasons == []
    assert assessment.recommended_stop_loss is not None
    assert assessment.recommended_take_profit is not None


async def test_evaluate_rejects_symbol_not_in_whitelist(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(
        make_rule(account.user_id, RiskRuleType.SYMBOL_WHITELIST, None, config={"symbols": ["ETHUSDT"]})
    )
    order = make_order(account, symbol="BTCUSDT")

    with pytest.raises(RiskLimitExceededError):
        await engine.evaluate(uow, order=order, account=account)


async def test_evaluate_allows_whitelisted_symbol(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(
        make_rule(account.user_id, RiskRuleType.SYMBOL_WHITELIST, None, config={"symbols": ["BTCUSDT"]})
    )
    order = make_order(account, symbol="BTCUSDT")

    assessment = await engine.evaluate(uow, order=order, account=account)

    assert assessment.approved


async def test_evaluate_rejects_when_max_open_trades_reached(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(make_rule(account.user_id, RiskRuleType.MAX_OPEN_TRADES, Decimal("1")))
    await uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="ETHUSDT",
            quantity=Decimal("2"),
            avg_entry_price=Decimal("2000"),
            realized_pnl=Decimal("0"),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )
    order = make_order(account, symbol="BTCUSDT")

    with pytest.raises(RiskLimitExceededError):
        await engine.evaluate(uow, order=order, account=account)


async def test_evaluate_rejects_order_notional_over_limit(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(make_rule(account.user_id, RiskRuleType.MAX_POSITION_NOTIONAL, Decimal("10000")))
    order = make_order(account, quantity=Decimal("1"), price=Decimal("50000"))

    with pytest.raises(RiskLimitExceededError):
        await engine.evaluate(uow, order=order, account=account)


async def test_evaluate_skips_notional_check_without_a_reference_price(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(make_rule(account.user_id, RiskRuleType.MAX_POSITION_NOTIONAL, Decimal("10000")))
    # A MARKET order with no existing position in this symbol carries no
    # price this engine can evaluate notional against — fails open.
    order = make_order(account, quantity=Decimal("1"), price=None)

    assessment = await engine.evaluate(uow, order=order, account=account)

    assert assessment.approved


async def test_evaluate_raises_when_emergency_stop_is_active(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_state.upsert(
        RiskState(
            id=uuid.uuid4(),
            user_id=account.user_id,
            circuit_breaker=CircuitBreakerState.CLOSED,
            updated_at=_NOW,
            emergency_stop=True,
            emergency_stop_reason="manual halt",
        )
    )
    order = make_order(account)

    with pytest.raises(EmergencyStopActiveError):
        await engine.evaluate(uow, order=order, account=account)


async def test_evaluate_raises_when_circuit_breaker_is_open(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_state.upsert(
        RiskState(
            id=uuid.uuid4(),
            user_id=account.user_id,
            circuit_breaker=CircuitBreakerState.OPEN,
            updated_at=_NOW,
            circuit_breaker_reason="daily loss breached",
            circuit_breaker_resume_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    order = make_order(account)

    with pytest.raises(CircuitBreakerTrippedError):
        await engine.evaluate(uow, order=order, account=account)


async def test_evaluate_auto_resumes_expired_circuit_breaker(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    # `resume_at` must be in the past relative to the *real* wall clock
    # `evaluate` reads internally (`datetime.now(UTC)`), not the fixed
    # `_NOW` fixture time other tests use for constructing fixtures.
    real_now = datetime.now(UTC)
    await uow.risk_state.upsert(
        RiskState(
            id=uuid.uuid4(),
            user_id=account.user_id,
            circuit_breaker=CircuitBreakerState.OPEN,
            updated_at=real_now - timedelta(hours=2),
            circuit_breaker_reason="daily loss breached",
            circuit_breaker_resume_at=real_now - timedelta(minutes=1),
        )
    )
    order = make_order(account)

    assessment = await engine.evaluate(uow, order=order, account=account)

    assert assessment.approved
    state = await uow.risk_state.get_for_user(account.user_id)
    assert state.circuit_breaker == CircuitBreakerState.CLOSED


async def test_record_fill_trips_circuit_breaker_on_max_daily_loss(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.risk_rules.add(make_rule(account.user_id, RiskRuleType.MAX_DAILY_LOSS, Decimal("100")))

    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-60"))
    state = await uow.risk_state.get_for_user(account.user_id)
    assert state.circuit_breaker == CircuitBreakerState.CLOSED

    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-50"))
    state = await uow.risk_state.get_for_user(account.user_id)
    assert state.daily_loss == Decimal("110")
    assert state.circuit_breaker == CircuitBreakerState.OPEN

    order = make_order(account)
    with pytest.raises(CircuitBreakerTrippedError):
        await engine.evaluate(uow, order=order, account=account)


async def test_record_fill_trips_circuit_breaker_on_consecutive_losses(uow) -> None:
    engine = RiskEngine(consecutive_loss_limit=2)
    account = make_account()

    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-10"))
    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-10"))

    state = await uow.risk_state.get_for_user(account.user_id)
    assert state.consecutive_losses == 2
    assert state.circuit_breaker == CircuitBreakerState.OPEN


async def test_record_fill_winning_trade_resets_streak_without_tripping(uow) -> None:
    engine = RiskEngine(consecutive_loss_limit=2)
    account = make_account()

    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-10"))
    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("25"))

    state = await uow.risk_state.get_for_user(account.user_id)
    assert state.consecutive_losses == 0
    assert state.circuit_breaker == CircuitBreakerState.CLOSED


async def test_compute_equity_combines_cash_and_position_notional(uow) -> None:
    engine = RiskEngine()
    account = make_account()
    await uow.wallets.upsert(
        Wallet(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            asset="USDT",
            free=Decimal("5000"),
            locked=Decimal("500"),
            updated_at=_NOW,
        )
    )
    await uow.positions.upsert(
        Position(
            id=uuid.uuid4(),
            exchange_account_id=account.id,
            symbol="BTCUSDT",
            quantity=Decimal("0.1"),
            avg_entry_price=Decimal("50000"),
            realized_pnl=Decimal("0"),
            opened_at=_NOW,
            updated_at=_NOW,
        )
    )

    equity = await engine.compute_equity(uow, account)

    assert equity == Decimal("5000") + Decimal("500") + Decimal("0.1") * Decimal("50000")


async def test_set_emergency_stop_and_reset_circuit_breaker_use_lazily_created_state(uow) -> None:
    engine = RiskEngine()
    user_id = uuid.uuid4()

    state = await engine.set_emergency_stop(uow, user_id=user_id, active=True, reason="ops halt")
    assert state.emergency_stop is True
    assert state.emergency_stop_reason == "ops halt"

    state = await engine.set_emergency_stop(uow, user_id=user_id, active=False, reason=None)
    assert state.emergency_stop is False

    state = await engine.reset_circuit_breaker(uow, user_id=user_id)
    assert state.circuit_breaker == CircuitBreakerState.CLOSED


async def test_suggest_position_size_with_no_account_returns_zero_quantity(uow) -> None:
    engine = RiskEngine()

    quantity, stop_loss_price, take_profit_price = await engine.suggest_position_size(
        uow, account=None, side=OrderSide.BUY, entry_price=Decimal("100")
    )

    assert quantity == Decimal("0")
    assert stop_loss_price == Decimal("98.00")
    assert take_profit_price == Decimal("104.00")
