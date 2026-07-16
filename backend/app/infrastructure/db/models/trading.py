"""Trading bounded context: the platform's own account, ledger, and order
records. Mirrors `app.domain.trading.entities` — see that module's
docstring for how this differs from `app.domain.exchange`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.exchange.enums import OrderSide, OrderType, TimeInForce
from app.domain.trading.enums import AccountStatus, PlatformOrderStatus
from app.infrastructure.db.base import Base
from app.infrastructure.db.types import portable_enum

# Crypto balances/prices need more headroom than fiat money columns:
# 18 fractional digits covers wei-scale assets, 18 integer digits covers
# even the largest supply x price combinations Binance lists.
_AMOUNT = Numeric(36, 18)


class ExchangeAccountModel(Base):
    __tablename__ = "exchange_accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "exchange", "label", name="uq_exchange_accounts_user_id_exchange_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    is_testnet: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[AccountStatus] = mapped_column(
        portable_enum(AccountStatus), nullable=False, default=AccountStatus.ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WalletModel(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("exchange_account_id", "asset", name="uq_wallets_exchange_account_id_asset"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exchange_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset: Mapped[str] = mapped_column(String(20), nullable=False)
    free: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    locked: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderModel(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("client_order_id", name="uq_orders_client_order_id"),
        UniqueConstraint(
            "exchange_account_id", "exchange_order_id", name="uq_orders_exchange_account_id_exchange_order_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exchange_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    signal_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("signals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[OrderSide] = mapped_column(portable_enum(OrderSide), nullable=False)
    type: Mapped[OrderType] = mapped_column(portable_enum(OrderType), nullable=False)
    status: Mapped[PlatformOrderStatus] = mapped_column(portable_enum(PlatformOrderStatus), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    executed_quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    cumulative_quote_quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    price: Mapped[Decimal | None] = mapped_column(_AMOUNT, nullable=True)
    stop_price: Mapped[Decimal | None] = mapped_column(_AMOUNT, nullable=True)
    time_in_force: Mapped[TimeInForce | None] = mapped_column(portable_enum(TimeInForce), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange_order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PositionModel(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("exchange_account_id", "symbol", name="uq_positions_exchange_account_id_symbol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exchange_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    avg_entry_price: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    realized_pnl: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TradeModel(Base):
    """A single execution ("fill"); see `app.domain.trading.entities.Trade`."""

    __tablename__ = "trade_history"
    __table_args__ = (
        UniqueConstraint(
            "exchange_account_id", "exchange_trade_id", name="uq_trade_history_exchange_account_id_exchange_trade_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exchange_account_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("exchange_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[OrderSide] = mapped_column(portable_enum(OrderSide), nullable=False)
    price: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    quote_quantity: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    commission: Mapped[Decimal] = mapped_column(_AMOUNT, nullable=False)
    commission_asset: Mapped[str | None] = mapped_column(String(20), nullable=True)
    exchange_trade_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
