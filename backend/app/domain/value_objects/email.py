"""Email value object.

A small, immutable wrapper that guarantees any ``Email`` instance in the
system is syntactically valid and normalized (lower-cased). Using this
instead of a bare ``str`` moves validation to the boundary of the domain
instead of scattering ``re.match`` calls through use cases.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.exceptions import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_RE.match(normalized):
            raise ValidationError(f"'{self.value}' is not a valid email address")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
