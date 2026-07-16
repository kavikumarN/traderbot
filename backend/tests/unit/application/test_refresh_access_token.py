from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.auth.login import LoginCommand, LoginUseCase
from app.application.use_cases.auth.refresh_access_token import (
    RefreshAccessTokenCommand,
    RefreshAccessTokenUseCase,
)
from app.domain.entities.refresh_token import RefreshToken
from app.domain.exceptions import InvalidTokenError, TokenRevokedError
from tests.unit.application.helpers import seed_user


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_revokes_the_old_one(uow, uow_factory, password_hasher, token_service) -> None:
    await seed_user(uow, password_hasher)
    login_result = await LoginUseCase(uow_factory, password_hasher, token_service).execute(
        LoginCommand(email="trader@example.com", password="correcthorse1")
    )
    use_case = RefreshAccessTokenUseCase(uow_factory, token_service)

    result = await use_case.execute(RefreshAccessTokenCommand(raw_refresh_token=login_result.refresh_token))

    assert result.refresh_token != login_result.refresh_token
    old = await uow.refresh_tokens.get_by_hash(token_service.hash_refresh_token(login_result.refresh_token))
    assert old is not None
    assert old.is_revoked()
    new = await uow.refresh_tokens.get_by_hash(token_service.hash_refresh_token(result.refresh_token))
    assert new is not None
    assert not new.is_revoked()


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_token(uow_factory, token_service) -> None:
    use_case = RefreshAccessTokenUseCase(uow_factory, token_service)
    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshAccessTokenCommand(raw_refresh_token="does-not-exist"))


@pytest.mark.asyncio
async def test_refresh_rejects_expired_token(uow, uow_factory, password_hasher, token_service) -> None:
    user = await seed_user(uow, password_hasher)
    now = datetime.now(UTC)
    expired = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_service.hash_refresh_token("expired-raw-token"),
        issued_at=now - timedelta(days=8),
        expires_at=now - timedelta(days=1),
    )
    await uow.refresh_tokens.add(expired)
    use_case = RefreshAccessTokenUseCase(uow_factory, token_service)

    with pytest.raises(InvalidTokenError):
        await use_case.execute(RefreshAccessTokenCommand(raw_refresh_token="expired-raw-token"))


@pytest.mark.asyncio
async def test_reusing_a_revoked_token_revokes_all_sessions(uow, uow_factory, password_hasher, token_service) -> None:
    await seed_user(uow, password_hasher)
    login_result = await LoginUseCase(uow_factory, password_hasher, token_service).execute(
        LoginCommand(email="trader@example.com", password="correcthorse1")
    )
    use_case = RefreshAccessTokenUseCase(uow_factory, token_service)
    first_rotation = await use_case.execute(
        RefreshAccessTokenCommand(raw_refresh_token=login_result.refresh_token)
    )

    # Reusing the already-rotated (now revoked) token is treated as theft.
    with pytest.raises(TokenRevokedError):
        await use_case.execute(RefreshAccessTokenCommand(raw_refresh_token=login_result.refresh_token))

    # Defensive revocation nukes the *entire* session tree, including the
    # token that was legitimately issued by the first rotation.
    still_valid = await uow.refresh_tokens.get_by_hash(
        token_service.hash_refresh_token(first_rotation.refresh_token)
    )
    assert still_valid is not None
    assert still_valid.is_revoked()
