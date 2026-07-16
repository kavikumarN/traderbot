"""Register a new user.

The default role is granted to every self-registered user; elevated roles
(``admin``, etc.) can only be granted afterwards by an administrator through
the role-assignment use case — registration never accepts a caller-supplied
role.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.entities.user import User
from app.domain.exceptions import EntityAlreadyExistsError
from app.domain.value_objects.email import Email
from app.domain.value_objects.password import PlainPassword

DEFAULT_ROLE_NAME = "trader"


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    first_name: str
    last_name: str


@dataclass(frozen=True, slots=True)
class RegisterUserResult:
    user_id: uuid.UUID
    email: str


class RegisterUserUseCase:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        password_hasher: PasswordHasher,
        password_min_length: int,
        default_role_name: str = DEFAULT_ROLE_NAME,
    ) -> None:
        self._uow_factory = uow_factory
        self._password_hasher = password_hasher
        self._password_min_length = password_min_length
        self._default_role_name = default_role_name

    async def execute(self, command: RegisterUserCommand) -> RegisterUserResult:
        email = Email(command.email)
        password = PlainPassword(command.password, min_length=self._password_min_length)

        async with self._uow_factory() as uow:
            if await uow.users.get_by_email(str(email)) is not None:
                raise EntityAlreadyExistsError("User", "email", str(email))

            now = datetime.now(UTC)
            user = User(
                id=uuid.uuid4(),
                email=email,
                hashed_password=self._password_hasher.hash(password),
                first_name=command.first_name.strip(),
                last_name=command.last_name.strip(),
                is_active=True,
                is_verified=False,
                created_at=now,
                updated_at=now,
            )
            user.assign_role(self._default_role_name)

            await uow.users.add(user)
            await uow.commit()

        return RegisterUserResult(user_id=user.id, email=str(user.email))
