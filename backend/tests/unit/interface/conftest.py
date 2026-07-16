"""API-level test fixtures.

Builds the real FastAPI app (real routes, real middleware, real exception
handlers) but overrides the composition-root providers so requests never
touch Postgres or Redis — everything runs against the same in-memory fakes
used by the application-layer tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.application.use_cases.news.list_news import ListNewsUseCase
from app.core.config import Settings
from app.interface.api.deps import (
    get_list_news_use_case,
    get_market_data_reader,
    get_password_hasher,
    get_settings_dep,
    get_strategy_engine,
    get_token_blacklist,
    get_token_service,
    get_uow_factory,
)
from app.main import create_app
from tests.fakes.fake_exchange_client import FakeExchangeClient
from tests.fakes.fake_news_feed_client import FakeNewsFeedClient
from tests.fakes.fake_security import FakePasswordHasher, FakeTokenBlacklist, FakeTokenService
from tests.fakes.fake_unit_of_work import FakeUnitOfWork, make_uow_factory


def make_test_settings() -> Settings:
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        redis_url="redis://localhost:6379/0",
        jwt_secret_key="test-secret-key-thats-long-enough-1234567890",
        password_min_length=10,
        environment="test",
    )


@pytest.fixture
def test_uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def fake_market_data_reader() -> FakeExchangeClient:
    """Also satisfies `IMarketDataReader` — see that class's own docstring.
    Exposed as a fixture (rather than baked silently into `client`) so
    tests that need a price set `ticker_result` on it before requesting."""
    return FakeExchangeClient()


@pytest.fixture
def fake_news_feed_client() -> FakeNewsFeedClient:
    """Exposed as a fixture (rather than baked silently into `client`) so
    tests that need articles set `.responses[url]` before requesting."""
    return FakeNewsFeedClient()


@pytest_asyncio.fixture
async def client(
    test_uow: FakeUnitOfWork,
    fake_market_data_reader: FakeExchangeClient,
    fake_news_feed_client: FakeNewsFeedClient,
) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=make_test_settings())

    # Singletons, not factories: fakes carry state (issued tokens, blacklist
    # entries) that must survive across the several requests one test makes.
    token_service = FakeTokenService()
    token_blacklist = FakeTokenBlacklist()
    password_hasher = FakePasswordHasher()

    app.dependency_overrides[get_uow_factory] = lambda: make_uow_factory(test_uow)
    app.dependency_overrides[get_password_hasher] = lambda: password_hasher
    app.dependency_overrides[get_token_service] = lambda: token_service
    app.dependency_overrides[get_token_blacklist] = lambda: token_blacklist
    app.dependency_overrides[get_settings_dep] = lambda: make_test_settings()
    # No lifespan runs under `ASGITransport`, so `request.app.state.strategy_engine`
    # (set in `app.main`'s lifespan) never exists — tests that care about the
    # live runtime override this themselves; everything else gets `None`,
    # which `UpdateStrategyStatusUseCase` already treats as "no engine to sync".
    app.dependency_overrides[get_strategy_engine] = lambda: None
    # Same reasoning: `get_market_data_reader`'s real chain reads
    # `request.app.state.trading_mode`, which the lifespan never set here.
    app.dependency_overrides[get_market_data_reader] = lambda: fake_market_data_reader
    # `get_list_news_use_case` otherwise returns the real process-wide
    # singleton (real HTTP fetches against real news sites) — tests get a
    # fresh `ListNewsUseCase` per test wrapping the fake feed client instead.
    app.dependency_overrides[get_list_news_use_case] = lambda: ListNewsUseCase(fake_news_feed_client)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
