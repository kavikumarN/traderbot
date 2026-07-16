from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.strategy.entities import Backtest, Signal, Strategy


class StrategyRepository(ABC):
    @abstractmethod
    async def add(self, strategy: Strategy) -> None: ...

    @abstractmethod
    async def get_by_id(self, strategy_id: uuid.UUID) -> Strategy | None: ...

    @abstractmethod
    async def list_for_user(self, user_id: uuid.UUID) -> list[Strategy]: ...

    @abstractmethod
    async def list_active(self) -> list[Strategy]:
        """Every strategy in `LIVE` or `PAPER_TRADING` status, across every
        user — what `StrategyEngine` polls at startup to know which
        strategies to actually run."""
        ...

    @abstractmethod
    async def update(self, strategy: Strategy) -> None: ...


class SignalRepository(ABC):
    @abstractmethod
    async def add(self, signal: Signal) -> None: ...

    @abstractmethod
    async def get_by_id(self, signal_id: uuid.UUID) -> Signal | None: ...

    @abstractmethod
    async def list_for_strategy(
        self, strategy_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Signal]: ...

    @abstractmethod
    async def update(self, signal: Signal) -> None: ...


class BacktestRepository(ABC):
    @abstractmethod
    async def add(self, backtest: Backtest) -> None: ...

    @abstractmethod
    async def get_by_id(self, backtest_id: uuid.UUID) -> Backtest | None: ...

    @abstractmethod
    async def list_for_strategy(self, strategy_id: uuid.UUID) -> list[Backtest]: ...

    @abstractmethod
    async def update(self, backtest: Backtest) -> None: ...
