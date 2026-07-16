"""Composition root.

Every dependency below is a thin FastAPI ``Depends`` provider. Singletons
(engine, session factory, Redis client, password hasher, token service) are
created once in ``app.main``'s lifespan and stored on ``app.state``; this
module only reads them back out and wires per-request objects (unit of
work, use cases) on top. No use case or route ever imports SQLAlchemy,
Redis, or PyJWT directly — only these provider functions do.
"""

from __future__ import annotations

import httpx
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.market_data_repository import MarketDataRepository
from app.application.ports.password_hasher import PasswordHasher
from app.application.ports.token_blacklist import TokenBlacklist
from app.application.ports.token_service import AccessTokenPayload, TokenService
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.services.backtest_engine import BacktestEngine
from app.application.services.execution_service import ExecutionService
from app.application.services.order_service import OrderService
from app.application.services.portfolio_service import PortfolioService
from app.application.services.risk_engine import RiskEngine
from app.application.services.signal_manager import SignalManager
from app.application.services.strategy_engine import StrategyEngine
from app.application.services.strategy_loader import StrategyLoader
from app.application.services.trading_service import TradingService
from app.application.use_cases.auth.login import LoginUseCase
from app.application.use_cases.auth.logout import LogoutUseCase
from app.application.use_cases.auth.refresh_access_token import RefreshAccessTokenUseCase
from app.application.use_cases.auth.register_user import RegisterUserUseCase
from app.application.use_cases.backtesting.get_backtest import GetBacktestUseCase
from app.application.use_cases.backtesting.list_backtests import ListBacktestsUseCase
from app.application.use_cases.backtesting.run_backtest import RunBacktestUseCase
from app.application.use_cases.portfolio.get_performance import GetPerformanceUseCase
from app.application.use_cases.portfolio.get_summary import GetPortfolioSummaryUseCase
from app.application.use_cases.portfolio.list_positions import ListPositionsUseCase
from app.application.use_cases.portfolio.list_trade_history import ListTradeHistoryUseCase
from app.application.use_cases.portfolio.list_wallets import ListWalletsUseCase
from app.application.use_cases.risk.calculate_position_size import CalculatePositionSizeUseCase
from app.application.use_cases.risk.create_risk_rule import CreateRiskRuleUseCase
from app.application.use_cases.risk.delete_risk_rule import DeleteRiskRuleUseCase
from app.application.use_cases.risk.get_risk_rule import GetRiskRuleUseCase
from app.application.use_cases.risk.get_risk_state import GetRiskStateUseCase
from app.application.use_cases.risk.list_risk_rules import ListRiskRulesUseCase
from app.application.use_cases.risk.reset_circuit_breaker import ResetCircuitBreakerUseCase
from app.application.use_cases.risk.set_emergency_stop import SetEmergencyStopUseCase
from app.application.use_cases.risk.update_risk_rule import UpdateRiskRuleUseCase
from app.application.use_cases.roles.assign_role_to_user import (
    AssignRoleToUserUseCase,
    RevokeRoleFromUserUseCase,
)
from app.application.use_cases.roles.create_role import CreateRoleUseCase
from app.application.use_cases.roles.list_permissions import ListPermissionsUseCase
from app.application.use_cases.roles.list_roles import ListRolesUseCase
from app.application.use_cases.roles.manage_role_permissions import (
    GrantPermissionUseCase,
    RevokePermissionUseCase,
)
from app.application.use_cases.roles.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from app.application.use_cases.strategies.create_strategy import CreateStrategyUseCase
from app.application.use_cases.strategies.get_strategy import GetStrategyUseCase
from app.application.use_cases.strategies.list_signals import ListSignalsUseCase
from app.application.use_cases.strategies.list_strategies import ListStrategiesUseCase
from app.application.use_cases.strategies.update_strategy_status import UpdateStrategyStatusUseCase
from app.application.use_cases.users.get_user import GetUserUseCase
from app.application.use_cases.users.list_users import ListUsersUseCase
from app.application.use_cases.users.set_user_active import SetUserActiveUseCase
from app.core.config import Settings
from app.domain.entities.user import User
from app.domain.exceptions import (
    EntityNotFoundError,
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
    TokenRevokedError,
)
from app.domain.exchange.ports.account_reader import IAccountReader
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.domain.exchange.ports.order_placer import IOrderPlacer
from app.domain.exchange.ports.rate_limiter import RateLimiter
from app.domain.strategy.plugin_manager import PluginManager, default_plugin_manager
from app.infrastructure.binance.adapter import BinanceExchangeAdapter
from app.infrastructure.binance.http_client import BinanceHttpClient
from app.infrastructure.binance.retry import RetryPolicy
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.paper_trading.adapter import PaperTradingExchangeAdapter
from app.interface.api.websocket_manager import WebSocketManager

bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access token returned by /auth/login")


# --- Singletons pulled off app.state -----------------------------------------------------


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return request.app.state.session_factory


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


def get_password_hasher(request: Request) -> PasswordHasher:
    return request.app.state.password_hasher


def get_token_service(request: Request) -> TokenService:
    return request.app.state.token_service


def get_token_blacklist(request: Request) -> TokenBlacklist:
    return request.app.state.token_blacklist


def get_binance_httpx_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.binance_http_client


def get_binance_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.binance_rate_limiter


def get_websocket_manager(request: Request) -> WebSocketManager:
    return request.app.state.websocket_manager


def get_market_data_repository(request: Request) -> MarketDataRepository:
    return request.app.state.market_data_repository


def get_trading_mode(request: Request) -> str:
    return request.app.state.trading_mode


def get_paper_trading_adapter(request: Request) -> PaperTradingExchangeAdapter:
    """The paper-trading simulator is a process-wide singleton (see
    `app.main`), not something rebuilt per request — it holds real mutable
    state (balances, resting orders) that must survive between calls."""
    return request.app.state.paper_trading_adapter


def get_strategy_engine(request: Request) -> StrategyEngine:
    """The Strategy Engine (Phase 7) is a process-wide singleton (see
    `app.main`) — it owns one `asyncio.Task` per running strategy for the
    lifetime of the process, not something rebuilt per request."""
    return request.app.state.strategy_engine


# --- Binance exchange integration --------------------------------------------------------------


def get_binance_http_client(
    settings: Settings = Depends(get_settings_dep),
    httpx_client: httpx.AsyncClient = Depends(get_binance_httpx_client),
    rate_limiter: RateLimiter = Depends(get_binance_rate_limiter),
) -> BinanceHttpClient:
    return BinanceHttpClient(
        base_url=settings.binance_rest_base_url,
        api_key=settings.binance_api_key,
        api_secret=settings.binance_api_secret.get_secret_value() if settings.binance_api_secret else None,
        rate_limiter=rate_limiter,
        http_client=httpx_client,
        recv_window_ms=settings.binance_recv_window_ms,
        retry_policy=RetryPolicy(
            max_attempts=settings.binance_max_retries,
            base_delay_seconds=settings.binance_retry_base_delay_seconds,
        ),
    )


def get_exchange_client(
    trading_mode: str = Depends(get_trading_mode),
    http: BinanceHttpClient = Depends(get_binance_http_client),
    paper_trading_adapter: PaperTradingExchangeAdapter = Depends(get_paper_trading_adapter),
) -> ExchangeClient:
    """The full Exchange Adapter Pattern port. Most routes should prefer
    one of the narrower providers below (Interface Segregation).

    In "paper" trading mode this returns the shared `PaperTradingExchangeAdapter`
    singleton instead of building a fresh `BinanceExchangeAdapter` — no order
    placed through this dependency ever reaches Binance while paper trading
    is on, regardless of which route pulled it in.
    """
    if trading_mode == "paper":
        return paper_trading_adapter
    return BinanceExchangeAdapter(http)


def get_market_data_reader(
    exchange_client: ExchangeClient = Depends(get_exchange_client),
) -> IMarketDataReader:
    return exchange_client


def get_account_reader(
    exchange_client: ExchangeClient = Depends(get_exchange_client),
) -> IAccountReader:
    return exchange_client


def get_order_placer(
    exchange_client: ExchangeClient = Depends(get_exchange_client),
) -> IOrderPlacer:
    return exchange_client


# --- Unit of work --------------------------------------------------------------------------


def get_uow_factory(
    session_factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
) -> UnitOfWorkFactory:
    return SqlAlchemyUnitOfWork.factory(session_factory)


# --- Risk engine (Phase 8) -----------------------------------------------------------------


def get_risk_engine() -> RiskEngine:
    return RiskEngine()


# --- Trading engine (Phase 6) ----------------------------------------------------------------


def get_execution_service() -> ExecutionService:
    return ExecutionService()


def get_order_service() -> OrderService:
    return OrderService()


def get_trading_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    execution_service: ExecutionService = Depends(get_execution_service),
    order_service: OrderService = Depends(get_order_service),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    settings: Settings = Depends(get_settings_dep),
) -> TradingService:
    return TradingService(
        uow_factory, execution_service, order_service, risk_engine, trading_mode=settings.trading_mode
    )


def get_create_risk_rule_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> CreateRiskRuleUseCase:
    return CreateRiskRuleUseCase(uow_factory)


def get_list_risk_rules_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListRiskRulesUseCase:
    return ListRiskRulesUseCase(uow_factory)


def get_get_risk_rule_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> GetRiskRuleUseCase:
    return GetRiskRuleUseCase(uow_factory)


def get_update_risk_rule_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> UpdateRiskRuleUseCase:
    return UpdateRiskRuleUseCase(uow_factory)


def get_delete_risk_rule_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> DeleteRiskRuleUseCase:
    return DeleteRiskRuleUseCase(uow_factory)


def get_get_risk_state_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> GetRiskStateUseCase:
    return GetRiskStateUseCase(uow_factory, risk_engine)


def get_set_emergency_stop_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> SetEmergencyStopUseCase:
    return SetEmergencyStopUseCase(uow_factory, risk_engine)


def get_reset_circuit_breaker_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> ResetCircuitBreakerUseCase:
    return ResetCircuitBreakerUseCase(uow_factory, risk_engine)


def get_calculate_position_size_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> CalculatePositionSizeUseCase:
    return CalculatePositionSizeUseCase(uow_factory, risk_engine)


# --- Portfolio (Phase 9) -------------------------------------------------------------------


def get_portfolio_service() -> PortfolioService:
    return PortfolioService()


def get_get_portfolio_summary_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> GetPortfolioSummaryUseCase:
    return GetPortfolioSummaryUseCase(uow_factory, portfolio_service, market_data)


def get_list_wallets_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> ListWalletsUseCase:
    return ListWalletsUseCase(uow_factory, portfolio_service)


def get_list_positions_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> ListPositionsUseCase:
    return ListPositionsUseCase(uow_factory, portfolio_service, market_data)


def get_list_trade_history_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> ListTradeHistoryUseCase:
    return ListTradeHistoryUseCase(uow_factory, portfolio_service)


def get_get_performance_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> GetPerformanceUseCase:
    return GetPerformanceUseCase(uow_factory, portfolio_service, market_data)


# --- Strategy engine (Phase 7) -----------------------------------------------------------------


def get_plugin_manager() -> PluginManager:
    """The built-in strategy catalog registers itself against this same
    process-wide `default_plugin_manager` on import (see
    `app.domain.strategy.plugins`, imported once by `app.main`) — this
    provider just hands that registry back out."""
    return default_plugin_manager


def get_strategy_loader(
    plugin_manager: PluginManager = Depends(get_plugin_manager),
) -> StrategyLoader:
    return StrategyLoader(plugin_manager)


def get_signal_manager(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    trading_service: TradingService = Depends(get_trading_service),
) -> SignalManager:
    return SignalManager(uow_factory, trading_service)


def get_create_strategy_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    plugin_manager: PluginManager = Depends(get_plugin_manager),
) -> CreateStrategyUseCase:
    return CreateStrategyUseCase(uow_factory, plugin_manager)


def get_get_strategy_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> GetStrategyUseCase:
    return GetStrategyUseCase(uow_factory)


def get_list_strategies_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListStrategiesUseCase:
    return ListStrategiesUseCase(uow_factory)


def get_list_signals_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListSignalsUseCase:
    return ListSignalsUseCase(uow_factory)


def get_update_strategy_status_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    strategy_engine: StrategyEngine = Depends(get_strategy_engine),
) -> UpdateStrategyStatusUseCase:
    return UpdateStrategyStatusUseCase(uow_factory, strategy_engine)


# --- Backtesting (Phase 10) ---------------------------------------------------------------------


def get_backtest_engine() -> BacktestEngine:
    return BacktestEngine()


def get_run_backtest_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
    engine: BacktestEngine = Depends(get_backtest_engine),
    strategy_loader: StrategyLoader = Depends(get_strategy_loader),
) -> RunBacktestUseCase:
    return RunBacktestUseCase(uow_factory, market_data, engine=engine, strategy_loader=strategy_loader)


def get_list_backtests_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListBacktestsUseCase:
    return ListBacktestsUseCase(uow_factory)


def get_get_backtest_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> GetBacktestUseCase:
    return GetBacktestUseCase(uow_factory)


# --- Auth use cases --------------------------------------------------------------------------


def get_register_user_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    settings: Settings = Depends(get_settings_dep),
) -> RegisterUserUseCase:
    return RegisterUserUseCase(uow_factory, password_hasher, settings.password_min_length)


def get_login_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    password_hasher: PasswordHasher = Depends(get_password_hasher),
    token_service: TokenService = Depends(get_token_service),
) -> LoginUseCase:
    return LoginUseCase(uow_factory, password_hasher, token_service)


def get_refresh_access_token_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    token_service: TokenService = Depends(get_token_service),
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(uow_factory, token_service)


def get_logout_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    token_service: TokenService = Depends(get_token_service),
    token_blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> LogoutUseCase:
    return LogoutUseCase(uow_factory, token_service, token_blacklist)


# --- User use cases --------------------------------------------------------------------------


def get_get_user_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> GetUserUseCase:
    return GetUserUseCase(uow_factory)


def get_list_users_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListUsersUseCase:
    return ListUsersUseCase(uow_factory)


def get_set_user_active_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> SetUserActiveUseCase:
    return SetUserActiveUseCase(uow_factory)


# --- Role / permission use cases --------------------------------------------------------------


def get_create_role_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> CreateRoleUseCase:
    return CreateRoleUseCase(uow_factory)


def get_list_roles_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListRolesUseCase:
    return ListRolesUseCase(uow_factory)


def get_list_permissions_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListPermissionsUseCase:
    return ListPermissionsUseCase(uow_factory)


def get_grant_permission_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> GrantPermissionUseCase:
    return GrantPermissionUseCase(uow_factory)


def get_revoke_permission_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> RevokePermissionUseCase:
    return RevokePermissionUseCase(uow_factory)


def get_assign_role_to_user_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> AssignRoleToUserUseCase:
    return AssignRoleToUserUseCase(uow_factory)


def get_revoke_role_from_user_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> RevokeRoleFromUserUseCase:
    return RevokeRoleFromUserUseCase(uow_factory)


def get_resolve_user_permissions_use_case(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ResolveUserPermissionsUseCase:
    return ResolveUserPermissionsUseCase(uow_factory)


# --- Authentication / authorization dependencies ----------------------------------------------


async def get_current_access_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token_service: TokenService = Depends(get_token_service),
    token_blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> AccessTokenPayload:
    if credentials is None:
        raise InvalidTokenError("Missing bearer token")

    payload = token_service.decode_access_token(credentials.credentials)
    if await token_blacklist.is_blacklisted(payload.jti):
        raise TokenRevokedError()
    return payload


async def get_current_user(
    payload: AccessTokenPayload = Depends(get_current_access_token_payload),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> User:
    async with uow_factory() as uow:
        user = await uow.users.get_by_id(payload.user_id)

    if user is None:
        raise EntityNotFoundError("User", payload.user_id)
    if not user.is_active:
        raise InactiveUserError()
    return user


def require_permission(permission_code: str):
    """Dependency factory: ``Depends(require_permission("users:read"))``."""

    async def _check(
        payload: AccessTokenPayload = Depends(get_current_access_token_payload),
        resolve_permissions: ResolveUserPermissionsUseCase = Depends(
            get_resolve_user_permissions_use_case
        ),
    ) -> AccessTokenPayload:
        granted = await resolve_permissions.execute(set(payload.role_names))
        if permission_code not in granted:
            raise PermissionDeniedError(permission_code)
        return payload

    return _check
