"""SQLAlchemy ORM models.

These are persistence models only — they never leak past the repository
boundary. Application and domain code sees ``app.domain.*`` entities;
translation between the two happens entirely inside
``app.infrastructure.repositories``.

Split into one module per bounded context; this ``__init__`` re-exports
everything so existing call sites (``from app.infrastructure.db.models
import UserModel``) and Alembic's ``env.py`` are unaffected by the split.
"""

from __future__ import annotations

from app.infrastructure.db.models.audit import AuditLogModel
from app.infrastructure.db.models.identity import (
    PermissionModel,
    RefreshTokenModel,
    RoleModel,
    UserModel,
    role_permissions,
    user_roles,
)
from app.infrastructure.db.models.marketdata import (
    CandleModel,
    MarketTickModel,
    OrderBookSnapshotModel,
    VolumeStatsModel,
)
from app.infrastructure.db.models.notification import NotificationModel
from app.infrastructure.db.models.risk import RiskRuleModel, RiskStateModel
from app.infrastructure.db.models.strategy import BacktestModel, SignalModel, StrategyModel
from app.infrastructure.db.models.trading import (
    ExchangeAccountModel,
    OrderModel,
    PositionModel,
    TradeModel,
    WalletModel,
)

__all__ = [
    "AuditLogModel",
    "BacktestModel",
    "CandleModel",
    "ExchangeAccountModel",
    "MarketTickModel",
    "NotificationModel",
    "OrderBookSnapshotModel",
    "OrderModel",
    "PermissionModel",
    "PositionModel",
    "RefreshTokenModel",
    "RiskRuleModel",
    "RiskStateModel",
    "RoleModel",
    "SignalModel",
    "StrategyModel",
    "TradeModel",
    "UserModel",
    "VolumeStatsModel",
    "WalletModel",
    "role_permissions",
    "user_roles",
]
