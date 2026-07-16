"""Manually halt or resume an account's trading — the one risk control that
never auto-resumes (unlike the circuit breaker's cooldown), so a human
always has the last word over whether an account is allowed to trade."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.risk_engine import RiskEngine
from app.domain.risk.entities import RiskState


@dataclass(frozen=True, slots=True)
class SetEmergencyStopCommand:
    user_id: uuid.UUID
    active: bool
    reason: str | None = None


class SetEmergencyStopUseCase:
    def __init__(self, uow_factory: UnitOfWorkFactory, risk_engine: RiskEngine) -> None:
        self._uow_factory = uow_factory
        self._risk_engine = risk_engine

    async def execute(self, command: SetEmergencyStopCommand) -> RiskState:
        async with self._uow_factory() as uow:
            state = await self._risk_engine.set_emergency_stop(
                uow, user_id=command.user_id, active=command.active, reason=command.reason
            )
            await uow.commit()
        return state
