from __future__ import annotations

import pytest

from app.application.use_cases.auth.register_user import RegisterUserCommand, RegisterUserUseCase
from app.domain.exceptions import EntityAlreadyExistsError, ValidationError


@pytest.mark.asyncio
async def test_register_user_succeeds_and_grants_default_role(uow_factory, password_hasher) -> None:
    use_case = RegisterUserUseCase(uow_factory, password_hasher, password_min_length=10)

    result = await use_case.execute(
        RegisterUserCommand(
            email="new@example.com", password="correcthorse1", first_name="New", last_name="User"
        )
    )

    assert result.email == "new@example.com"
    stored = await uow_factory().users.get_by_id(result.user_id)
    assert stored is not None
    assert stored.has_role("trader")
    assert stored.hashed_password == "hashed::correcthorse1"
    assert stored.hashed_password != "correcthorse1"


@pytest.mark.asyncio
async def test_register_user_rejects_duplicate_email(uow_factory, password_hasher) -> None:
    use_case = RegisterUserUseCase(uow_factory, password_hasher, password_min_length=10)
    command = RegisterUserCommand(
        email="dup@example.com", password="correcthorse1", first_name="A", last_name="B"
    )
    await use_case.execute(command)

    with pytest.raises(EntityAlreadyExistsError):
        await use_case.execute(command)


@pytest.mark.asyncio
async def test_register_user_rejects_weak_password(uow_factory, password_hasher) -> None:
    use_case = RegisterUserUseCase(uow_factory, password_hasher, password_min_length=10)

    with pytest.raises(ValidationError):
        await use_case.execute(
            RegisterUserCommand(email="weak@example.com", password="short1", first_name="A", last_name="B")
        )
