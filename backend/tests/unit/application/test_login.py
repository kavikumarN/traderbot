from __future__ import annotations

import pytest

from app.application.use_cases.auth.login import LoginCommand, LoginUseCase
from app.domain.exceptions import InactiveUserError, InvalidCredentialsError
from tests.unit.application.helpers import seed_user as _seed_user


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(uow, uow_factory, password_hasher, token_service) -> None:
    await _seed_user(uow, password_hasher)
    use_case = LoginUseCase(uow_factory, password_hasher, token_service)

    result = await use_case.execute(LoginCommand(email="trader@example.com", password="correcthorse1"))

    assert result.access_token
    assert result.refresh_token
    stored_token = await uow.refresh_tokens.get_by_hash(token_service.hash_refresh_token(result.refresh_token))
    assert stored_token is not None
    assert stored_token.user_id == result.user_id


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(uow, uow_factory, password_hasher, token_service) -> None:
    await _seed_user(uow, password_hasher)
    use_case = LoginUseCase(uow_factory, password_hasher, token_service)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginCommand(email="trader@example.com", password="wrong-password-1"))


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(uow_factory, password_hasher, token_service) -> None:
    use_case = LoginUseCase(uow_factory, password_hasher, token_service)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginCommand(email="ghost@example.com", password="whatever12"))


@pytest.mark.asyncio
async def test_login_rejects_inactive_user(uow, uow_factory, password_hasher, token_service) -> None:
    await _seed_user(uow, password_hasher, is_active=False)
    use_case = LoginUseCase(uow_factory, password_hasher, token_service)

    with pytest.raises(InactiveUserError):
        await use_case.execute(LoginCommand(email="trader@example.com", password="correcthorse1"))
