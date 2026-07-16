"""SQLAlchemy adapter for `MarketDataRepository`.

`MarketDataService` runs for the lifetime of the process, outside any HTTP
request — so unlike every other repository in this codebase, this one
can't borrow a request-scoped session from `UnitOfWork`. It holds a
`session_factory` instead and opens one short-lived session per call,
committing and closing immediately after. This bounds each unit of work to
a single write (or read) so a long-running background task never pins one
connection — or accumulates one session's identity-map state — for hours
at a stretch.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.market_data_repository import MarketDataRepository
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.marketdata.entities import MarketTick, PersistedCandle
from app.infrastructure.repositories.sqlalchemy_candle_repository import SqlAlchemyCandleRepository
from app.infrastructure.repositories.sqlalchemy_market_tick_repository import (
    SqlAlchemyMarketTickRepository,
)
from app.infrastructure.repositories.sqlalchemy_order_book_repository import (
    SqlAlchemyOrderBookRepository,
)
from app.infrastructure.repositories.sqlalchemy_volume_stats_repository import (
    SqlAlchemyVolumeStatsRepository,
)

# `get_recent_trades` has no caller-supplied time range (unlike
# `get_candles`) — this bounds the underlying `list_range` scan window.
_RECENT_TRADES_WINDOW = timedelta(hours=24)


def _candle_to_persisted(candle: Candle) -> PersistedCandle:
    return PersistedCandle(
        symbol=candle.symbol,
        interval=candle.interval,
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        quote_volume=candle.quote_volume,
        trade_count=candle.trade_count,
    )


def _trade_to_tick(trade: Trade) -> MarketTick:
    return MarketTick(
        symbol=trade.symbol,
        trade_id=trade.trade_id,
        price=trade.price,
        quantity=trade.quantity,
        quote_quantity=trade.quote_quantity,
        traded_at=trade.traded_at,
        is_buyer_maker=trade.is_buyer_maker,
    )


class SqlAlchemyMarketDataRepository(MarketDataRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def save_candle(self, candle: Candle) -> None:
        async with self._session_factory() as session:
            await SqlAlchemyCandleRepository(session).upsert(_candle_to_persisted(candle))
            await session.commit()

    async def save_trade(self, trade: Trade) -> None:
        async with self._session_factory() as session:
            await SqlAlchemyMarketTickRepository(session).add(_trade_to_tick(trade))
            await session.commit()

    async def save_order_book(self, snapshot: OrderBookSnapshot) -> None:
        async with self._session_factory() as session:
            await SqlAlchemyOrderBookRepository(session).upsert(snapshot)
            await session.commit()

    async def save_volume_stats(self, ticker: Ticker) -> None:
        async with self._session_factory() as session:
            await SqlAlchemyVolumeStatsRepository(session).upsert(ticker)
            await session.commit()

    async def get_candles(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        async with self._session_factory() as session:
            return await SqlAlchemyCandleRepository(session).list_range(symbol, interval, start=start, end=end)

    async def get_recent_trades(self, symbol: str, *, limit: int = 100) -> list[MarketTick]:
        end = datetime.now(UTC)
        start = end - _RECENT_TRADES_WINDOW
        async with self._session_factory() as session:
            ticks = await SqlAlchemyMarketTickRepository(session).list_range(
                symbol, start=start, end=end, limit=limit
            )
        # `list_range` is oldest-first (chart-friendly); "recent" reads
        # newest-first.
        return list(reversed(ticks))

    async def get_order_book(self, symbol: str) -> OrderBookSnapshot | None:
        async with self._session_factory() as session:
            return await SqlAlchemyOrderBookRepository(session).get_latest(symbol)

    async def get_volume_stats(self, symbol: str) -> Ticker | None:
        async with self._session_factory() as session:
            return await SqlAlchemyVolumeStatsRepository(session).get_latest(symbol)
