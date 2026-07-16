"""Port for user persistence.

An abstract base class, not a ``Protocol`` — every method here must be
implemented, and mypy/IDE support for "go to implementation" works better
against an ABC. The concrete implementation lives in
``app.infrastructure.repositories.sqlalchemy_user_repository``.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from app.domain.entities.user import User


class UserRepository(ABC):
    @abstractmethod
    async def add(self, user: User) -> None: ...

    @abstractmethod
    async def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def list(self, *, offset: int = 0, limit: int = 50) -> list[User]: ...

    @abstractmethod
    async def count(self) -> int: ...

    @abstractmethod
    async def update(self, user: User) -> None: ...
