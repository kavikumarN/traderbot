"""Port for the authenticated (per-account) event stream — order fills and
balance changes pushed in real time, instead of polling ``get_open_orders``."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.domain.exchange.models.account import AssetBalance, ExchangeOrder


@dataclass(frozen=True, slots=True)
class OrderUpdateEvent:
    order: ExchangeOrder


@dataclass(frozen=True, slots=True)
class BalanceUpdateEvent:
    balances: tuple[AssetBalance, ...]


UserDataEvent = OrderUpdateEvent | BalanceUpdateEvent


class IUserDataStream(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Obtains a session (e.g. a listen key) and opens the connection."""
        ...

    @abstractmethod
    def events(self) -> AsyncIterator[UserDataEvent]: ...

    @abstractmethod
    async def close(self) -> None: ...
