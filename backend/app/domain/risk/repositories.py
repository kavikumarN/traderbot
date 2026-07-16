from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.risk.entities import RiskRule, RiskState


class RiskRuleRepository(ABC):
    @abstractmethod
    async def add(self, rule: RiskRule) -> None: ...

    @abstractmethod
    async def get_by_id(self, rule_id: uuid.UUID) -> RiskRule | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> list[RiskRule]: ...

    @abstractmethod
    async def list_active_for_strategy(self, strategy_id: uuid.UUID) -> list[RiskRule]:
        """Active rules that apply to `strategy_id` — both rules scoped
        directly to it and account-wide rules (`strategy_id IS NULL`) for
        the same owning user."""
        ...

    @abstractmethod
    async def update(self, rule: RiskRule) -> None: ...

    @abstractmethod
    async def delete(self, rule_id: uuid.UUID) -> None: ...


class RiskStateRepository(ABC):
    """One row per user — the circuit-breaker/emergency-stop/daily-loss
    runtime state `RiskEngine` reads and mutates on every evaluation."""

    @abstractmethod
    async def get_for_user(self, user_id: uuid.UUID) -> RiskState | None: ...

    @abstractmethod
    async def upsert(self, state: RiskState) -> None: ...
