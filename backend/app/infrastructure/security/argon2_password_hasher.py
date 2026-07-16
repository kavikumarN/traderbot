"""Argon2id password hashing.

Argon2id is the OWASP-recommended default for new applications: it is
memory-hard (resists GPU/ASIC cracking) and includes the side-channel
resistance of Argon2i with the GPU resistance of Argon2d. Default cost
parameters come from ``argon2-cffi`` and are re-tuned by the library
maintainers as hardware improves.
"""

from __future__ import annotations

from argon2 import PasswordHasher as Argon2Hasher
from argon2 import exceptions as argon2_exceptions

from app.application.ports.password_hasher import PasswordHasher
from app.domain.value_objects.password import PlainPassword


class Argon2PasswordHasher(PasswordHasher):
    def __init__(self) -> None:
        self._hasher = Argon2Hasher()

    def hash(self, password: PlainPassword) -> str:
        return self._hasher.hash(password.value)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        try:
            return self._hasher.verify(hashed_password, plain_password)
        except (argon2_exceptions.Argon2Error, ValueError):
            # ValueError covers argon2.exceptions.InvalidHashError, which is
            # (surprisingly) not a subclass of Argon2Error — malformed input
            # must still resolve to "not a match", never an exception.
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        try:
            return self._hasher.check_needs_rehash(hashed_password)
        except (argon2_exceptions.Argon2Error, ValueError):
            return True
