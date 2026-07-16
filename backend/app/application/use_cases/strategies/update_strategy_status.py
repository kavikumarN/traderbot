"""Strategy lifecycle transitions: DRAFT/VALIDATED/BACKTESTING -> PAPER_TRADING
-> LIVE -> PAUSED, or -> RETIRED from anywhere. `Strategy` itself only
guards the two transitions specific enough to need real invariants
(`promote_to_live`, `pause`); starting paper trading and retiring are
simple enough to set directly here.

When a `StrategyEngine` is supplied (it won't be in tests that don't care
about the live runtime), this use case keeps it in sync: entering a
tradeable status starts the strategy's polling task, leaving one stops it —
so activating/pausing a strategy through the API takes effect immediately,
not just in the database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.strategy_engine import StrategyEngine
from app.domain.exceptions import EntityNotFoundError, ValidationError
from app.domain.strategy.entities import Strategy
from app.domain.strategy.enums import StrategyStatus

_PAPER_TRADING_SOURCE_STATUSES = frozenset(
    {StrategyStatus.DRAFT, StrategyStatus.VALIDATED, StrategyStatus.BACKTESTING}
)
_TRADEABLE_STATUSES = frozenset({StrategyStatus.LIVE, StrategyStatus.PAPER_TRADING})


class StrategyStatusAction(StrEnum):
    START_PAPER_TRADING = "start_paper_trading"
    PROMOTE_TO_LIVE = "promote_to_live"
    PAUSE = "pause"
    RETIRE = "retire"


@dataclass(frozen=True, slots=True)
class UpdateStrategyStatusCommand:
    strategy_id: uuid.UUID
    user_id: uuid.UUID
    action: StrategyStatusAction


class UpdateStrategyStatusUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, strategy_engine: StrategyEngine | None = None) -> None:
        self._uow_factory = uow_factory
        self._engine = strategy_engine

    async def execute(self, command: UpdateStrategyStatusCommand) -> Strategy:
        async with self._uow_factory() as uow:
            strategy = await uow.strategies.get_by_id(command.strategy_id)
            if strategy is None or strategy.user_id != command.user_id:
                raise EntityNotFoundError("Strategy", command.strategy_id)

            try:
                _apply(strategy, command.action)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            strategy.updated_at = datetime.now(UTC)
            await uow.strategies.update(strategy)
            await uow.commit()

        if self._engine is not None:
            if strategy.status in _TRADEABLE_STATUSES:
                await self._engine.start_strategy(strategy)
            else:
                await self._engine.stop_strategy(strategy.id)

        return strategy


def _apply(strategy: Strategy, action: StrategyStatusAction) -> None:
    if action == StrategyStatusAction.START_PAPER_TRADING:
        if strategy.status not in _PAPER_TRADING_SOURCE_STATUSES:
            raise ValueError(f"Cannot start paper trading from {strategy.status.value}")
        strategy.status = StrategyStatus.PAPER_TRADING
    elif action == StrategyStatusAction.PROMOTE_TO_LIVE:
        strategy.promote_to_live()
    elif action == StrategyStatusAction.PAUSE:
        strategy.pause()
    elif action == StrategyStatusAction.RETIRE:
        strategy.status = StrategyStatus.RETIRED
