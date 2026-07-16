from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.entities.refresh_token import RefreshToken
from app.domain.entities.role import Role
from app.domain.entities.user import User
from app.domain.exceptions import ValidationError
from app.domain.value_objects.email import Email


def make_user(**overrides: object) -> User:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        id=uuid.uuid4(),
        email=Email("user@example.com"),
        hashed_password="hashed",
        first_name="Ada",
        last_name="Lovelace",
        is_active=True,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return User(**defaults)  # type: ignore[arg-type]


class TestUser:
    def test_deactivate_then_activate(self) -> None:
        user = make_user()
        user.deactivate()
        assert user.is_active is False
        user.activate()
        assert user.is_active is True

    def test_cannot_assign_role_to_inactive_user(self) -> None:
        user = make_user(is_active=False)
        with pytest.raises(ValidationError):
            user.assign_role("trader")

    def test_assign_and_revoke_role(self) -> None:
        user = make_user()
        user.assign_role("trader")
        assert user.has_role("trader")
        user.revoke_role("trader")
        assert not user.has_role("trader")

    def test_full_name(self) -> None:
        user = make_user(first_name="Ada", last_name="Lovelace")
        assert user.full_name == "Ada Lovelace"


class TestRole:
    def test_grant_and_revoke_permission(self) -> None:
        role = Role(id=uuid.uuid4(), name="admin", description="")
        role.grant("users:read")
        assert role.has_permission("users:read")
        role.revoke("users:read")
        assert not role.has_permission("users:read")

    def test_revoking_unknown_permission_is_a_no_op(self) -> None:
        role = Role(id=uuid.uuid4(), name="admin", description="")
        role.revoke("users:read")  # must not raise
        assert not role.has_permission("users:read")


class TestRefreshToken:
    def _make(self, **overrides: object) -> RefreshToken:
        now = datetime.now(UTC)
        defaults: dict[object, object] = dict(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            token_hash="hash",
            issued_at=now,
            expires_at=now + timedelta(days=7),
        )
        defaults.update(overrides)
        return RefreshToken(**defaults)  # type: ignore[arg-type]

    def test_is_active_when_fresh(self) -> None:
        token = self._make()
        assert token.is_active(datetime.now(UTC))

    def test_is_expired_past_expiry(self) -> None:
        token = self._make(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        now = datetime.now(UTC)
        assert token.is_expired(now)
        assert not token.is_active(now)

    def test_revoke_marks_inactive_and_records_replacement(self) -> None:
        token = self._make()
        replacement_id = uuid.uuid4()
        now = datetime.now(UTC)
        token.revoke(now, replaced_by=replacement_id)
        assert token.is_revoked()
        assert token.replaced_by_token_id == replacement_id
        assert not token.is_active(now)
