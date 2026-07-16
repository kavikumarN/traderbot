"""Permission entity.

A permission is a fine-grained capability, identified by a stable ``code``
in ``resource:action`` form (e.g. ``users:read``, ``roles:manage``). The
catalog of permissions is managed by administrators; individual users never
hold permissions directly — they hold them through roles (see ``Role``).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(slots=True)
class Permission:
    id: uuid.UUID
    code: str
    description: str

    def __post_init__(self) -> None:
        if ":" not in self.code:
            raise ValueError(
                f"Permission code must be in 'resource:action' form, got {self.code!r}"
            )
