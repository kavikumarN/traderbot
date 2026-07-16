"""Register a new strategy in DRAFT status.

Validates `strategy_type`/`parameters` immediately by constructing and
initializing a real plugin instance — the same validation `StrategyLoader`
would otherwise only discover the next time the engine tried to load this
strategy. Failing fast here means a bad config never gets past creation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.strategy.entities import Strategy
from app.domain.strategy.enums import StrategyStatus
from app.domain.strategy.plugin import StrategyContext
from app.domain.strategy.plugin_manager import PluginManager, default_plugin_manager


@dataclass(frozen=True, slots=True)
class CreateStrategyCommand:
    user_id: uuid.UUID
    name: str
    description: str
    symbol: str
    strategy_type: str
    parameters: dict[str, Any] = field(default_factory=dict)


class CreateStrategyUseCase:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, plugin_manager: PluginManager = default_plugin_manager
    ) -> None:
        self._uow_factory = uow_factory
        self._plugin_manager = plugin_manager

    async def execute(self, command: CreateStrategyCommand) -> Strategy:
        plugin_cls = self._plugin_manager.get(command.strategy_type)
        probe = plugin_cls(
            StrategyContext(strategy_id=uuid.uuid4(), symbol=command.symbol.upper(), parameters=command.parameters)
        )
        await probe.initialize()
        await probe.shutdown()

        now = datetime.now(UTC)
        strategy = Strategy(
            id=uuid.uuid4(),
            user_id=command.user_id,
            name=command.name,
            description=command.description,
            symbol=command.symbol.upper(),
            status=StrategyStatus.DRAFT,
            version=1,
            created_at=now,
            updated_at=now,
            config={"strategy_type": command.strategy_type, "parameters": command.parameters},
        )
        async with self._uow_factory() as uow:
            await uow.strategies.add(strategy)
            await uow.commit()
        return strategy
