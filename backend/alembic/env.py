from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import (  # noqa: F401 — registers models on Base.metadata
    AuditLogModel,
    BacktestModel,
    CandleModel,
    ExchangeAccountModel,
    MarketTickModel,
    NotificationModel,
    OrderBookSnapshotModel,
    OrderModel,
    PermissionModel,
    PositionModel,
    RefreshTokenModel,
    RiskRuleModel,
    RoleModel,
    SignalModel,
    StrategyModel,
    TradeModel,
    UserModel,
    VolumeStatsModel,
    WalletModel,
    role_permissions,
    user_roles,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# The application's own settings are the single source of truth for the
# connection string — never duplicate it in alembic.ini.
config.set_main_option("sqlalchemy.url", str(get_settings().database_url))

# `create_hypertable()` (see the Phase 4 migration) silently creates its own
# index on each hypertable's time-partitioning column. Neither model
# declares it, so without this filter every `--autogenerate` run proposes
# dropping it.
_TIMESCALE_MANAGED_INDEXES = {"candles_open_time_idx", "market_data_traded_at_idx"}


def include_object(object, name, type_, reflected, compare_to) -> bool:
    if type_ == "index" and name in _TIMESCALE_MANAGED_INDEXES:
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
