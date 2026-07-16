from __future__ import annotations

import uuid

import pytest

from app.application.use_cases.strategies.get_strategy import GetStrategyUseCase
from app.domain.exceptions import EntityNotFoundError
from tests.unit.application.strategies.helpers import make_strategy


@pytest.mark.asyncio
async def test_get_returns_own_strategy(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    use_case = GetStrategyUseCase(uow_factory)

    result = await use_case.execute(user_id=strategy.user_id, strategy_id=strategy.id)

    assert result.id == strategy.id


@pytest.mark.asyncio
async def test_get_nonexistent_strategy_raises(uow_factory) -> None:
    use_case = GetStrategyUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(user_id=uuid.uuid4(), strategy_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_get_another_users_strategy_raises(uow, uow_factory) -> None:
    strategy = make_strategy()
    await uow.strategies.add(strategy)
    use_case = GetStrategyUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(user_id=uuid.uuid4(), strategy_id=strategy.id)
