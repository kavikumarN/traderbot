from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exchange.models.market_data import Ticker
from app.domain.marketdata.repositories import VolumeStatsRepository
from app.infrastructure.db.models import VolumeStatsModel


def _to_domain(model: VolumeStatsModel) -> Ticker:
    return Ticker(
        symbol=model.symbol,
        last_price=model.last_price,
        bid_price=model.bid_price,
        ask_price=model.ask_price,
        high_price=model.high_price,
        low_price=model.low_price,
        volume=model.volume,
        quote_volume=model.quote_volume,
        price_change_percent=model.price_change_percent,
        open_time=model.open_time,
        close_time=model.close_time,
    )


class SqlAlchemyVolumeStatsRepository(VolumeStatsRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, ticker: Ticker) -> None:
        stmt = insert(VolumeStatsModel).values(
            symbol=ticker.symbol,
            last_price=ticker.last_price,
            bid_price=ticker.bid_price,
            ask_price=ticker.ask_price,
            high_price=ticker.high_price,
            low_price=ticker.low_price,
            volume=ticker.volume,
            quote_volume=ticker.quote_volume,
            price_change_percent=ticker.price_change_percent,
            open_time=ticker.open_time,
            close_time=ticker.close_time,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[VolumeStatsModel.symbol],
            set_={
                "last_price": stmt.excluded.last_price,
                "bid_price": stmt.excluded.bid_price,
                "ask_price": stmt.excluded.ask_price,
                "high_price": stmt.excluded.high_price,
                "low_price": stmt.excluded.low_price,
                "volume": stmt.excluded.volume,
                "quote_volume": stmt.excluded.quote_volume,
                "price_change_percent": stmt.excluded.price_change_percent,
                "open_time": stmt.excluded.open_time,
                "close_time": stmt.excluded.close_time,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def get_latest(self, symbol: str) -> Ticker | None:
        model = await self._session.get(VolumeStatsModel, symbol)
        return _to_domain(model) if model else None
