"""Password value object.

``PlainPassword`` enforces the domain's strength policy on construction and
is only ever passed to a ``PasswordHasher`` port — it is never persisted and
must not appear in logs or ``repr()`` output. The policy's minimum length is
injected by the caller (see ``app.application.use_cases.auth``) rather than
read from settings here, so the domain layer stays free of infrastructure
concerns; ``DEFAULT_MIN_LENGTH`` is the sane default when no policy is given.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.exceptions import ValidationError

DEFAULT_MIN_LENGTH = 10
_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")


@dataclass(frozen=True, slots=True)
class PlainPassword:
    value: str
    min_length: int = DEFAULT_MIN_LENGTH

    def __post_init__(self) -> None:
        if len(self.value) < self.min_length:
            raise ValidationError(f"Password must be at least {self.min_length} characters long")
        if not _HAS_LETTER.search(self.value):
            raise ValidationError("Password must contain at least one letter")
        if not _HAS_DIGIT.search(self.value):
            raise ValidationError("Password must contain at least one digit")

    def __repr__(self) -> str:  # never leak the raw value into logs/tracebacks
        return "PlainPassword(***)"

    __str__ = __repr__
