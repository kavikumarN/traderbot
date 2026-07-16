from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases.auth.login import LoginCommand, LoginUseCase
from app.application.use_cases.auth.logout import LogoutCommand, LogoutUseCase
from tests.unit.application.helpers import seed_user


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token_and_blacklists_access_token(
    uow, uow_factory, password_hasher, token_service, token_blacklist
) -> None:
    await seed_user(uow, password_hasher)
    login_result = await LoginUseCase(uow_factory, password_hasher, token_service).execute(
        LoginCommand(email="trader@example.com", password="correcthorse1")
    )
    issued = token_service.create_access_token(
        user_id=login_result.user_id, email="trader@example.com", role_names={"trader"}
    )

    use_case = LogoutUseCase(uow_factory, token_service, token_blacklist)
    await use_case.execute(
        LogoutCommand(
            raw_refresh_token=login_result.refresh_token,
            access_token_jti=issued.payload.jti,
            access_token_expires_at=issued.payload.expires_at,
        )
    )

    stored = await uow.refresh_tokens.get_by_hash(token_service.hash_refresh_token(login_result.refresh_token))
    assert stored is not None
    assert stored.is_revoked()
    assert await token_blacklist.is_blacklisted(issued.payload.jti)


@pytest.mark.asyncio
async def test_logout_with_unknown_refresh_token_still_blacklists_access_token(
    uow_factory, token_service, token_blacklist
) -> None:
    use_case = LogoutUseCase(uow_factory, token_service, token_blacklist)

    await use_case.execute(
        LogoutCommand(
            raw_refresh_token="never-issued",
            access_token_jti="jti-orphan",
            access_token_expires_at=datetime.now(UTC),
        )
    )

    assert await token_blacklist.is_blacklisted("jti-orphan")
