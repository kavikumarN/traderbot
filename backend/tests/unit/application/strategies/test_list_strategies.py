from __future__ import annotations

import uuid

import pytest

from app.application.use_cases.strategies.list_strategies import ListStrategiesUseCase
from tests.unit.application.strategies.helpers import make_strategy


@pytest.mark.asyncio
async def test_list_returns_only_requesting_users_strategies(uow, uow_factory) -> None:
    user_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    mine_one = make_strategy(user_id=user_id)
    mine_two = make_strategy(user_id=user_id)
    someone_elses = make_strategy(user_id=other_user_id)
    await uow.strategies.add(mine_one)
    await uow.strategies.add(mine_two)
    await uow.strategies.add(someone_elses)
    use_case = ListStrategiesUseCase(uow_factory)

    result = await use_case.execute(user_id=user_id)

    assert {s.id for s in result} == {mine_one.id, mine_two.id}


@pytest.mark.asyncio
async def test_list_returns_empty_for_user_with_no_strategies(uow_factory) -> None:
    use_case = ListStrategiesUseCase(uow_factory)

    result = await use_case.execute(user_id=uuid.uuid4())

    assert result == []
