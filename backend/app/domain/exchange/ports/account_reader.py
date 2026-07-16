from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.exchange.models.account import AssetBalance


class IAccountReader(ABC):
    @abstractmethod
    async def get_balances(self) -> list[AssetBalance]: ...
