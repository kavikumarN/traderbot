"""Market-data bounded context. Mirrors `app.domain.marketdata.entities` —
see that module's docstring for why these two tables carry no surrogate
``id``: both are TimescaleDB hypertables (created in the Alembic migration
via ``create_hypertable``), and Timescale requires every unique constraint
— including the primary key — to include the hypertable's partitioning
(time) column. The natural key doubles as that constraint.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.exchange.enums import KlineInterval
from app.infrastructure.db.base import Base
from app.infrastructure.db.types import portable_enum

_PRICE = Numeric(36, 18)


class CandleModel(Base):
    __tablename__ = "candles"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    interval: Mapped[KlineInterval] = mapped_column(portable_enum(KlineInterval), primary_key=True)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    high: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    low: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    close: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    volume: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    quote_volume: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False)


class MarketTickModel(Base):
    __tablename__ = "market_data"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    traded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    trade_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    quote_quantity: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    is_buyer_maker: Mapped[bool] = mapped_column(Boolean, nullable=False)


class OrderBookSnapshotModel(Base):
    """Current-state table: one row per symbol, overwritten on every
    update (see `OrderBookRepository.upsert`). Depth history isn't kept —
    only the latest book is ever queried."""

    __tablename__ = "order_book_snapshots"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_update_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # `[{"price": "...", "quantity": "..."}, ...]`, best-to-worst ordered,
    # exactly as received from Binance — kept as JSONB rather than a child
    # table since it's always read/written as a single atomic snapshot.
    bids: Mapped[list] = mapped_column(JSONB, nullable=False)
    asks: Mapped[list] = mapped_column(JSONB, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class VolumeStatsModel(Base):
    """Current-state table: latest 24h ticker stats per symbol."""

    __tablename__ = "volume_stats"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    bid_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    ask_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    high_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    low_price: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    volume: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    quote_volume: Mapped[Decimal] = mapped_column(_PRICE, nullable=False)
    price_change_percent: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
