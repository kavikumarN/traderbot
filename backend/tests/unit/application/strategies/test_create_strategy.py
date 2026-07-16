from __future__ import annotations

import uuid

import pytest

from app.application.use_cases.strategies.create_strategy import CreateStrategyCommand, CreateStrategyUseCase
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.exceptions import InvalidStrategyConfigError, UnknownStrategyTypeError
from app.domain.strategy.plugin_manager import PluginManager
from tests.unit.application.strategies.helpers import DummyPlugin


def make_use_case(uow_factory, *, register: bool = True) -> CreateStrategyUseCase:
    plugin_manager = PluginManager()
    if register:
        plugin_manager.register(DummyPlugin)
    return CreateStrategyUseCase(uow_factory, plugin_manager)


@pytest.mark.asyncio
async def test_create_unknown_strategy_type_raises_before_persistence(uow, uow_factory) -> None:
    use_case = make_use_case(uow_factory, register=False)
    user_id = uuid.uuid4()
    command = CreateStrategyCommand(
        user_id=user_id, name="s", description="", symbol="btcusdt", strategy_type="UNKNOWN", parameters={}
    )

    with pytest.raises(UnknownStrategyTypeError):
        await use_case.execute(command)

    assert await uow.strategies.list_for_user(user_id) == []


@pytest.mark.asyncio
async def test_create_missing_quantity_raises_before_persistence(uow, uow_factory) -> None:
    use_case = make_use_case(uow_factory)
    user_id = uuid.uuid4()
    command = CreateStrategyCommand(
        user_id=user_id, name="s", description="", symbol="btcusdt", strategy_type="DUMMY", parameters={}
    )

    with pytest.raises(InvalidStrategyConfigError):
        await use_case.execute(command)

    assert await uow.strategies.list_for_user(user_id) == []


@pytest.mark.asyncio
async def test_create_success_persists_draft_strategy_with_config(uow, uow_factory) -> None:
    use_case = make_use_case(uow_factory)
    user_id = uuid.uuid4()
    command = CreateStrategyCommand(
        user_id=user_id,
        name="My strat",
        description="desc",
        symbol="btcusdt",
        strategy_type="DUMMY",
        parameters={"quantity": "0.01"},
    )

    strategy = await use_case.execute(command)

    assert strategy.status == StrategyStatus.DRAFT
    assert strategy.symbol == "BTCUSDT"
    assert strategy.config == {"strategy_type": "DUMMY", "parameters": {"quantity": "0.01"}}
    stored = await uow.strategies.get_by_id(strategy.id)
    assert stored is not None
    assert uow.committed
