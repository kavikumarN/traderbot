"""Application entrypoint: composition root for process-wide singletons and
the FastAPI app factory.

Run locally with ``uvicorn app.main:app --reload`` (see ``backend/Dockerfile``
for the production command).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.application.services.execution_service import ExecutionService
from app.application.services.market_data_service import MarketDataService
from app.application.services.order_service import OrderService
from app.application.services.risk_engine import RiskEngine
from app.application.services.signal_manager import SignalManager
from app.application.services.strategy_engine import StrategyEngine
from app.application.services.strategy_loader import StrategyLoader
from app.application.services.trading_service import TradingService
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.domain.exchange.enums import KlineInterval

# Side-effect import: every module under `app.domain.strategy.plugins`
# decorates its `StrategyPlugin` subclass with `@register_strategy` at
# import time. Importing the package here, once, at process startup is what
# populates `default_plugin_manager` before any request or the strategy
# engine itself can look a `strategy_type` up.
from app.domain.strategy import plugins as _strategy_plugins  # noqa: F401
from app.infrastructure.binance.adapter import BinanceExchangeAdapter
from app.infrastructure.binance.rate_limiter import InMemoryTokenBucketRateLimiter
from app.infrastructure.binance.ws.binance_market_data_stream import BinanceMarketDataStream
from app.infrastructure.binance_sdk.market_data_client import BinanceSdkMarketDataClient
from app.infrastructure.cache.redis_client import create_redis_client
from app.infrastructure.cache.redis_token_blacklist import RedisTokenBlacklist
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.paper_trading.adapter import PaperTradingExchangeAdapter
from app.infrastructure.repositories.sqlalchemy_market_data_repository import (
    SqlAlchemyMarketDataRepository,
)
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from app.infrastructure.security.jwt_token_service import JwtTokenService
from app.interface.api import health
from app.interface.api.deps import get_binance_http_client, get_binance_sdk_spot_client
from app.interface.api.errors import register_exception_handlers
from app.interface.api.middleware import RequestIdMiddleware
from app.interface.api.v1.router import api_v1_router
from app.interface.api.websocket_manager import WebSocketManager

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings)
        logger.info("Starting %s (%s)", settings.app_name, settings.environment)

        engine = create_engine(settings)
        session_factory = create_session_factory(engine)
        redis = create_redis_client(settings)

        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.redis = redis
        app.state.password_hasher = Argon2PasswordHasher()
        app.state.token_service = JwtTokenService(
            secret_key=settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
            access_token_expire_minutes=settings.access_token_expire_minutes,
            refresh_token_expire_days=settings.refresh_token_expire_days,
        )
        app.state.token_blacklist = RedisTokenBlacklist(redis)

        # Binance: one shared httpx client (connection pooling) and one
        # shared rate limiter (it tracks usage against Binance's actual
        # per-key/per-IP limit, so it must be a singleton, not built fresh
        # per request).
        app.state.binance_http_client = httpx.AsyncClient(timeout=10.0)
        app.state.binance_rate_limiter = InMemoryTokenBucketRateLimiter(
            {
                "REQUEST_WEIGHT": (
                    settings.binance_request_weight_limit,
                    settings.binance_request_weight_window_seconds,
                ),
                "ORDERS": (settings.binance_order_limit, settings.binance_order_window_seconds),
            }
        )

        # Market data (candles/ticker/order book/trades/exchange info) is
        # read via Binance's official Python connector
        # (https://developers.binance.com/en/docs/sdks-tools/connectors/python)
        # rather than the hand-rolled `BinanceMarketDataClient` above — one
        # shared client, reused everywhere a `BinanceExchangeAdapter` is
        # built below (paper trading's inner adapter, live trading mode).
        app.state.binance_sdk_market_data_client = BinanceSdkMarketDataClient(
            get_binance_sdk_spot_client(settings=settings)
        )

        # Trading engine (Phase 6): `trading_mode` gates which `ExchangeClient`
        # `app.interface.api.deps.get_exchange_client` hands out. In "paper"
        # mode that's this one shared `PaperTradingExchangeAdapter` — it must
        # be a singleton (not rebuilt per request) because it holds real
        # mutable state (balances, resting orders) that has to survive
        # between one request placing an order and a later one checking or
        # cancelling it. Its own market-data calls still go to Binance's
        # public endpoints (no API key needed) for real prices.
        app.state.trading_mode = settings.trading_mode
        app.state.paper_trading_adapter = (
            PaperTradingExchangeAdapter(
                BinanceExchangeAdapter(
                    get_binance_http_client(
                        settings=settings,
                        httpx_client=app.state.binance_http_client,
                        rate_limiter=app.state.binance_rate_limiter,
                    ),
                    market_data=app.state.binance_sdk_market_data_client,
                ),
                starting_balances={"USDT": settings.paper_trading_starting_balance_usdt},
                commission_rate=settings.paper_trading_commission_rate,
            )
            if settings.trading_mode == "paper"
            else None
        )

        # Market data engine (Phase 5): a background singleton, not a
        # per-request dependency — it owns its own Binance WebSocket
        # connections (separate from the REST httpx client above) for the
        # lifetime of the process. `market_data_symbols` defaults to
        # ["BTCUSDT", "ETHUSDT"] but can be set to `[]` to disable the
        # engine entirely (e.g. in environments that only need the REST proxy).
        app.state.websocket_manager = WebSocketManager()
        app.state.market_data_repository = SqlAlchemyMarketDataRepository(session_factory)
        market_data_service: MarketDataService | None = None
        if settings.market_data_symbols:
            market_data_service = MarketDataService(
                BinanceMarketDataStream(settings.binance_ws_base_url),
                app.state.market_data_repository,
                app.state.websocket_manager,
                symbols=settings.market_data_symbols,
                candle_intervals=[KlineInterval(value) for value in settings.market_data_candle_intervals],
                order_book_persist_interval_seconds=settings.market_data_order_book_persist_interval_seconds,
            )
            await market_data_service.start()
        app.state.market_data_service = market_data_service

        # Strategy engine (Phase 7): a background singleton, matching
        # `market_data_service`'s own shape — one `asyncio.Task` per active
        # strategy for the lifetime of the process, not a per-request
        # dependency. Shares the same `ExchangeClient` selection logic as
        # `app.interface.api.deps.get_exchange_client` (paper mode routes
        # through the one shared `PaperTradingExchangeAdapter` above; live
        # mode gets its own `BinanceExchangeAdapter` over the shared httpx
        # client/rate limiter, since a background task can't pull a
        # request-scoped one from `Depends`).
        uow_factory = SqlAlchemyUnitOfWork.factory(session_factory)
        strategy_exchange_client = (
            app.state.paper_trading_adapter
            if settings.trading_mode == "paper"
            else BinanceExchangeAdapter(
                get_binance_http_client(
                    settings=settings,
                    httpx_client=app.state.binance_http_client,
                    rate_limiter=app.state.binance_rate_limiter,
                ),
                market_data=app.state.binance_sdk_market_data_client,
            )
        )
        trading_service = TradingService(
            uow_factory, ExecutionService(), OrderService(), RiskEngine(), trading_mode=settings.trading_mode
        )
        strategy_engine = StrategyEngine(
            uow_factory,
            strategy_exchange_client,
            StrategyLoader(),
            SignalManager(uow_factory, trading_service),
        )
        await strategy_engine.start()
        app.state.strategy_engine = strategy_engine

        try:
            yield
        finally:
            logger.info("Shutting down %s", settings.app_name)
            await strategy_engine.stop()
            if market_data_service is not None:
                await market_data_service.stop()
            await engine.dispose()
            await redis.aclose()
            await app.state.binance_http_client.aclose()

    app = FastAPI(
        title=settings.app_name,
        description="Backend foundation for the algorithmic trading platform — auth, users, roles, permissions.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    # Auto-instruments request count/latency/in-progress by route+method+status
    # and exposes it at GET /metrics for Prometheus to scrape — see
    # k8s/monitoring/prometheus-configmap.yaml for the scrape config.
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
