from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.entities.refresh_token import RefreshToken


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def add(self, token: RefreshToken) -> None: ...

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def update(self, token: RefreshToken) -> None: ...

    @abstractmethod
    async def revoke_all_for_user(self, user_id: uuid.UUID, *, revoked_at: datetime) -> None: ...
