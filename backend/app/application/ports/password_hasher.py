"""Port for password hashing.

Kept separate from ``TokenService`` because the two have unrelated
lifecycles and failure modes (hashing is CPU-bound and pure; tokens involve
time and secrets). The concrete implementation
(``app.infrastructure.security.argon2_password_hasher``) uses Argon2id.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.value_objects.password import PlainPassword


class PasswordHasher(ABC):
    @abstractmethod
    def hash(self, password: PlainPassword) -> str: ...

    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool: ...

    @abstractmethod
    def needs_rehash(self, hashed_password: str) -> bool:
        """True if the hash was produced with weaker parameters than current policy."""
        ...
