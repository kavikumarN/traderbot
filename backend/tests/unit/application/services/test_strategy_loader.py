from __future__ import annotations

import pytest

from app.application.services.strategy_loader import StrategyLoader
from app.domain.strategy.exceptions import InvalidStrategyConfigError, UnknownStrategyTypeError
from app.domain.strategy.plugin_manager import PluginManager
from tests.unit.application.strategies.helpers import DummyPlugin, make_strategy


def make_loader() -> StrategyLoader:
    plugin_manager = PluginManager()
    plugin_manager.register(DummyPlugin)
    return StrategyLoader(plugin_manager)


@pytest.mark.asyncio
async def test_load_returns_initialized_plugin() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"strategy_type": "DUMMY", "parameters": {"quantity": "0.01"}})

    plugin = await loader.load(strategy)

    assert isinstance(plugin, DummyPlugin)
    assert plugin.initialized is True
    assert plugin.context.strategy_id == strategy.id
    assert plugin.context.symbol == strategy.symbol


@pytest.mark.asyncio
async def test_load_missing_strategy_type_raises() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"parameters": {"quantity": "0.01"}})

    with pytest.raises(InvalidStrategyConfigError):
        await loader.load(strategy)


@pytest.mark.asyncio
async def test_load_non_string_strategy_type_raises() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"strategy_type": 123, "parameters": {"quantity": "0.01"}})

    with pytest.raises(InvalidStrategyConfigError):
        await loader.load(strategy)


@pytest.mark.asyncio
async def test_load_non_dict_parameters_raises() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"strategy_type": "DUMMY", "parameters": ["not", "a", "dict"]})

    with pytest.raises(InvalidStrategyConfigError):
        await loader.load(strategy)


@pytest.mark.asyncio
async def test_load_unknown_strategy_type_raises() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"strategy_type": "NOT_REGISTERED", "parameters": {}})

    with pytest.raises(UnknownStrategyTypeError):
        await loader.load(strategy)


@pytest.mark.asyncio
async def test_load_propagates_plugin_initialize_error() -> None:
    loader = make_loader()
    strategy = make_strategy(config={"strategy_type": "DUMMY", "parameters": {}})

    with pytest.raises(InvalidStrategyConfigError):
        await loader.load(strategy)
