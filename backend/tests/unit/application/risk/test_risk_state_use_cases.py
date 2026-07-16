from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.risk_engine import RiskEngine
from app.application.use_cases.risk.calculate_position_size import (
    CalculatePositionSizeCommand,
    CalculatePositionSizeUseCase,
)
from app.application.use_cases.risk.get_risk_state import GetRiskStateUseCase
from app.application.use_cases.risk.reset_circuit_breaker import ResetCircuitBreakerUseCase
from app.application.use_cases.risk.set_emergency_stop import (
    SetEmergencyStopCommand,
    SetEmergencyStopUseCase,
)
from app.domain.exchange.enums import OrderSide
from app.domain.risk.enums import CircuitBreakerState
from app.domain.trading.entities import ExchangeAccount
from app.domain.trading.enums import AccountStatus

pytestmark = pytest.mark.asyncio


async def test_get_risk_state_lazily_creates_closed_state(uow_factory) -> None:
    use_case = GetRiskStateUseCase(uow_factory, RiskEngine())
    user_id = uuid.uuid4()

    state = await use_case.execute(user_id=user_id)

    assert state.user_id == user_id
    assert state.circuit_breaker == CircuitBreakerState.CLOSED
    assert state.is_trading_allowed is True


async def test_set_and_clear_emergency_stop(uow_factory) -> None:
    use_case = SetEmergencyStopUseCase(uow_factory, RiskEngine())
    user_id = uuid.uuid4()

    tripped = await use_case.execute(SetEmergencyStopCommand(user_id=user_id, active=True, reason="ops halt"))
    assert tripped.emergency_stop is True
    assert tripped.is_trading_allowed is False

    cleared = await use_case.execute(SetEmergencyStopCommand(user_id=user_id, active=False))
    assert cleared.emergency_stop is False
    assert cleared.is_trading_allowed is True


async def test_reset_circuit_breaker_clears_a_tripped_state(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    account = ExchangeAccount(
        id=uuid.uuid4(),
        user_id=user_id,
        exchange="PAPER",
        label="default",
        api_key_ciphertext="",
        api_key_last_four="0000",
        is_testnet=True,
        status=AccountStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    # A single losing fill trips this engine's (deliberately low) limit.
    engine = RiskEngine(consecutive_loss_limit=1)
    await engine.record_fill(uow, account=account, realized_pnl_delta=Decimal("-1"))
    state = await uow.risk_state.get_for_user(user_id)
    assert state.circuit_breaker == CircuitBreakerState.OPEN

    use_case = ResetCircuitBreakerUseCase(uow_factory, engine)
    reset_state = await use_case.execute(user_id=user_id)

    assert reset_state.circuit_breaker == CircuitBreakerState.CLOSED


async def test_calculate_position_size_with_no_account_yet_returns_zero_quantity(uow_factory) -> None:
    use_case = CalculatePositionSizeUseCase(uow_factory, RiskEngine())

    result = await use_case.execute(
        CalculatePositionSizeCommand(user_id=uuid.uuid4(), side=OrderSide.BUY, entry_price=Decimal("100"))
    )

    assert result.equity == Decimal("0")
    assert result.quantity == Decimal("0")
    assert result.stop_loss_price == Decimal("98.00")
    assert result.take_profit_price == Decimal("104.00")
