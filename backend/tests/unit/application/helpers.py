from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities.user import User
from app.domain.value_objects.email import Email
from app.domain.value_objects.password import PlainPassword

DEFAULT_PASSWORD = "correcthorse1"


async def seed_user(uow, password_hasher, *, email: str = "trader@example.com", is_active: bool = True) -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=Email(email),
        hashed_password=password_hasher.hash(PlainPassword(DEFAULT_PASSWORD, min_length=10)),
        first_name="Tess",
        last_name="Trader",
        is_active=is_active,
        is_verified=True,
        created_at=now,
        updated_at=now,
        role_names={"trader"},
    )
    await uow.users.add(user)
    return user
