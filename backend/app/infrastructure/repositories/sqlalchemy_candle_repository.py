from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exchange.enums import KlineInterval
from app.domain.marketdata.entities import PersistedCandle
from app.domain.marketdata.repositories import CandleRepository
from app.infrastructure.db.models import CandleModel

_CONFLICT_COLUMNS = [CandleModel.symbol, CandleModel.interval, CandleModel.open_time]


def _to_domain(model: CandleModel) -> PersistedCandle:
    return PersistedCandle(
        symbol=model.symbol,
        interval=model.interval,
        open_time=model.open_time,
        close_time=model.close_time,
        open=model.open,
        high=model.high,
        low=model.low,
        close=model.close,
        volume=model.volume,
        quote_volume=model.quote_volume,
        trade_count=model.trade_count,
    )


def _values(candle: PersistedCandle) -> dict:
    return {
        "symbol": candle.symbol,
        "interval": candle.interval,
        "open_time": candle.open_time,
        "close_time": candle.close_time,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "quote_volume": candle.quote_volume,
        "trade_count": candle.trade_count,
    }


_UPDATE_COLUMNS = ("close_time", "open", "high", "low", "close", "volume", "quote_volume", "trade_count")


class SqlAlchemyCandleRepository(CandleRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, candle: PersistedCandle) -> None:
        stmt = insert(CandleModel).values(**_values(candle))
        stmt = stmt.on_conflict_do_update(
            index_elements=_CONFLICT_COLUMNS,
            set_={column: getattr(stmt.excluded, column) for column in _UPDATE_COLUMNS},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def upsert_many(self, candles: list[PersistedCandle]) -> None:
        if not candles:
            return
        stmt = insert(CandleModel).values([_values(candle) for candle in candles])
        stmt = stmt.on_conflict_do_update(
            index_elements=_CONFLICT_COLUMNS,
            set_={column: getattr(stmt.excluded, column) for column in _UPDATE_COLUMNS},
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def list_range(
        self, symbol: str, interval: KlineInterval, *, start: datetime, end: datetime
    ) -> list[PersistedCandle]:
        stmt = (
            select(CandleModel)
            .where(
                CandleModel.symbol == symbol,
                CandleModel.interval == interval,
                CandleModel.open_time >= start,
                CandleModel.open_time <= end,
            )
            .order_by(CandleModel.open_time)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(model) for model in models]

    async def get_latest(self, symbol: str, interval: KlineInterval) -> PersistedCandle | None:
        stmt = (
            select(CandleModel)
            .where(CandleModel.symbol == symbol, CandleModel.interval == interval)
            .order_by(CandleModel.open_time.desc())
            .limit(1)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(model) if model else None
