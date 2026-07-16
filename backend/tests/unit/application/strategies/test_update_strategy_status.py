from __future__ import annotations

import uuid

import pytest

from app.application.services.strategy_engine import StrategyEngine
from app.application.use_cases.strategies.update_strategy_status import (
    StrategyStatusAction,
    UpdateStrategyStatusCommand,
    UpdateStrategyStatusUseCase,
)
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.plugin import StrategyContext
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.unit.application.strategies.helpers import (
    DummyPlugin,
    FakeStrategyLoader,
    SpySignalManager,
    make_strategy,
    make_ticker,
)


def make_engine(uow_factory, strategy) -> tuple[StrategyEngine, DummyPlugin]:
    plugin = DummyPlugin(
        StrategyContext(strategy_id=strategy.id, symbol=strategy.symbol, parameters={"quantity": "0.01"})
    )
    exchange = FakeExchangeClient()
    exchange.ticker_result = make_ticker()
    engine = StrategyEngine(
        uow_factory, exchange, FakeStrategyLoader(plugin=plugin), SpySignalManager(), poll_interval_seconds=5.0
    )
    return engine, plugin


@pytest.mark.asyncio
async def test_start_paper_trading_from_valid_sources(uow, uow_factory) -> None:
    for source_status in (StrategyStatus.DRAFT, StrategyStatus.VALIDATED, StrategyStatus.BACKTESTING):
        strategy = make_strategy(status=source_status)
        await uow.strategies.add(strategy)
        use_case = UpdateStrategyStatusUseCase(uow_factory)

        result = await use_case.execute(
            UpdateStrategyStatusCommand(
                strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.START_PAPER_TRADING
            )
        )

        assert result.status == StrategyStatus.PAPER_TRADING


@pytest.mark.asyncio
async def test_start_paper_trading_from_invalid_source_raises(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.LIVE)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    with pytest.raises(ValidationError):
        await use_case.execute(
            UpdateStrategyStatusCommand(
                strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.START_PAPER_TRADING
            )
        )


@pytest.mark.asyncio
async def test_promote_to_live_from_paper_trading(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    result = await use_case.execute(
        UpdateStrategyStatusCommand(
            strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PROMOTE_TO_LIVE
        )
    )

    assert result.status == StrategyStatus.LIVE


@pytest.mark.asyncio
async def test_promote_to_live_from_invalid_source_raises(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.DRAFT)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    with pytest.raises(ValidationError):
        await use_case.execute(
            UpdateStrategyStatusCommand(
                strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PROMOTE_TO_LIVE
            )
        )


@pytest.mark.asyncio
async def test_pause_from_live(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.LIVE)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    result = await use_case.execute(
        UpdateStrategyStatusCommand(strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PAUSE)
    )

    assert result.status == StrategyStatus.PAUSED


@pytest.mark.asyncio
async def test_pause_from_invalid_source_raises(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.PAPER_TRADING)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    with pytest.raises(ValidationError):
        await use_case.execute(
            UpdateStrategyStatusCommand(strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PAUSE)
        )


@pytest.mark.asyncio
async def test_retire_from_any_status(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.DRAFT)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    result = await use_case.execute(
        UpdateStrategyStatusCommand(strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.RETIRE)
    )

    assert result.status == StrategyStatus.RETIRED


@pytest.mark.asyncio
async def test_update_status_raises_for_another_users_strategy(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.DRAFT)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(
            UpdateStrategyStatusCommand(
                strategy_id=strategy.id, user_id=uuid.uuid4(), action=StrategyStatusAction.RETIRE
            )
        )


@pytest.mark.asyncio
async def test_update_status_raises_for_nonexistent_strategy(uow_factory) -> None:
    use_case = UpdateStrategyStatusUseCase(uow_factory)

    with pytest.raises(EntityNotFoundError):
        await use_case.execute(
            UpdateStrategyStatusCommand(
                strategy_id=uuid.uuid4(), user_id=uuid.uuid4(), action=StrategyStatusAction.RETIRE
            )
        )


@pytest.mark.asyncio
async def test_entering_tradeable_status_starts_engine_when_supplied(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.DRAFT)
    await uow.strategies.add(strategy)
    engine, plugin = make_engine(uow_factory, strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory, engine)

    result = await use_case.execute(
        UpdateStrategyStatusCommand(
            strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.START_PAPER_TRADING
        )
    )

    assert result.status == StrategyStatus.PAPER_TRADING
    assert strategy.id in engine.running_strategy_ids

    await engine.stop()


@pytest.mark.asyncio
async def test_leaving_tradeable_status_stops_engine_when_supplied(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.LIVE)
    await uow.strategies.add(strategy)
    engine, plugin = make_engine(uow_factory, strategy)
    await engine.start_strategy(strategy)
    assert strategy.id in engine.running_strategy_ids

    use_case = UpdateStrategyStatusUseCase(uow_factory, engine)
    result = await use_case.execute(
        UpdateStrategyStatusCommand(strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PAUSE)
    )

    assert result.status == StrategyStatus.PAUSED
    assert strategy.id not in engine.running_strategy_ids
    assert plugin.shutdown_called is True


@pytest.mark.asyncio
async def test_no_engine_interaction_when_engine_is_none(uow, uow_factory) -> None:
    strategy = make_strategy(status=StrategyStatus.LIVE)
    await uow.strategies.add(strategy)
    use_case = UpdateStrategyStatusUseCase(uow_factory, None)

    result = await use_case.execute(
        UpdateStrategyStatusCommand(strategy_id=strategy.id, user_id=strategy.user_id, action=StrategyStatusAction.PAUSE)
    )

    assert result.status == StrategyStatus.PAUSED
