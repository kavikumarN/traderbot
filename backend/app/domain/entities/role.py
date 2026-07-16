"""Role entity.

A role is a named bundle of permission codes. Roles are the unit users are
assigned; permissions are never attached to a user directly. Membership is
kept as a plain ``set[str]`` of permission codes rather than a list of
``Permission`` objects — role/permission composition is a simple set
operation and doesn't need the full permission catalog (description, id) to
answer "can a holder of this role do X?".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(slots=True)
class Role:
    id: uuid.UUID
    name: str
    description: str
    permission_codes: set[str] = field(default_factory=set)

    def grant(self, permission_code: str) -> None:
        self.permission_codes.add(permission_code)

    def revoke(self, permission_code: str) -> None:
        self.permission_codes.discard(permission_code)

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permission_codes
