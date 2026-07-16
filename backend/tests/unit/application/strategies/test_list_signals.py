from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.strategies.list_signals import ListSignalsUseCase
from app.domain.exceptions import EntityNotFoundError
from tests.unit.application.strategies.helpers import make_signal, make_strategy


@pytest.mark.asyncio
async def test_list_signals_returns_signals_for_own_strategy(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    now = datetime.now(UTC)
    signals = [
        make_signal(strategy_id=strategy.id, generated_at=now - timedelta(minutes=i)) for i in range(5)
    ]
    for signal in signals:
        await uow.signals.add(signal)
    use_case = ListSignalsUseCase(uow_factory)

    result = await use_case.execute(user_id=strategy.user_id, strategy_id=strategy.id)

    assert {s.id for s in result} == {s.id for s in signals}


@pytest.mark.asyncio
async def test_list_signals_respects_limit_and_offset(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    now = datetime.now(UTC)
    signals = [
        make_signal(strategy_id=strategy.id, generated_at=now - timedelta(minutes=i)) for i in range(5)
    ]
    for signal in signals:
        await uow.signals.add(signal)
    use_case = ListSignalsUseCase(uow_factory)

    result = await use_case.execute(user_id=strategy.user_id, strategy_id=strategy.id, limit=2, offset=1)

    assert len(result) == 2
    # Most recent first (index 0), so offset=1 skips it and returns the next two.
    assert [s.id for s in result] == [signals[1].id, signals[2].id]


@pytest.mark.asyncio
async def test_list_signals_raises_for_another_users_strategy(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    use_case = ListSignalsUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(user_id=uuid.uuid4(), strategy_id=strategy.id)


@pytest.mark.asyncio
async def test_list_signals_raises_for_nonexistent_strategy(uow_factory) -> None:
    use_case = ListSignalsUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(user_id=uuid.uuid4(), strategy_id=uuid.uuid4())
