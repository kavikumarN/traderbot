"""User entity — the aggregate root for the identity bounded context.

``User`` never stores a plaintext password: ``hashed_password`` is the
output of a ``PasswordHasher`` port, produced in the application layer.
State transitions (activate/deactivate, role membership) are methods on the
entity so invariants (e.g. "an inactive user cannot be granted a role")
live in one place instead of being re-implemented by every caller.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.domain.exceptions import ValidationError
from app.domain.value_objects.email import Email


@dataclass(slots=True)
class User:
    id: uuid.UUID
    email: Email
    hashed_password: str
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    role_names: set[str] = field(default_factory=set)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def deactivate(self) -> None:
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def verify(self) -> None:
        self.is_verified = True

    def change_password(self, new_hashed_password: str) -> None:
        if not new_hashed_password:
            raise ValidationError("Hashed password must not be empty")
        self.hashed_password = new_hashed_password

    def assign_role(self, role_name: str) -> None:
        if not self.is_active:
            raise ValidationError("Cannot assign a role to an inactive user")
        self.role_names.add(role_name)

    def revoke_role(self, role_name: str) -> None:
        self.role_names.discard(role_name)

    def has_role(self, role_name: str) -> bool:
        return role_name in self.role_names
