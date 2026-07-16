from __future__ import annotations

import pytest

from tests.fakes.fake_security import FakePasswordHasher, FakeTokenBlacklist, FakeTokenService
from tests.fakes.fake_unit_of_work import FakeUnitOfWork, make_uow_factory


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def uow_factory(uow: FakeUnitOfWork):
    return make_uow_factory(uow)


@pytest.fixture
def password_hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def token_service() -> FakeTokenService:
    return FakeTokenService()


@pytest.fixture
def token_blacklist() -> FakeTokenBlacklist:
    return FakeTokenBlacklist()
