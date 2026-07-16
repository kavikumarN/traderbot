"""Domain market-data model -> persisted-API response mapping."""

from __future__ import annotations

from app.domain.exchange.models.market_data import OrderBookSnapshot
from app.domain.marketdata.entities import MarketTick, PersistedCandle
from app.interface.api.schemas.market_data import (
    MarketTickResponse,
    PersistedCandleResponse,
    PersistedOrderBookLevelResponse,
    PersistedOrderBookResponse,
)


def persisted_candle_to_response(candle: PersistedCandle) -> PersistedCandleResponse:
    return PersistedCandleResponse(
        symbol=candle.symbol,
        interval=candle.interval.value,
        open_time=candle.open_time,
        close_time=candle.close_time,
        open=str(candle.open),
        high=str(candle.high),
        low=str(candle.low),
        close=str(candle.close),
        volume=str(candle.volume),
        quote_volume=str(candle.quote_volume),
        trade_count=candle.trade_count,
    )


def market_tick_to_response(tick: MarketTick) -> MarketTickResponse:
    return MarketTickResponse(
        symbol=tick.symbol,
        trade_id=tick.trade_id,
        price=str(tick.price),
        quantity=str(tick.quantity),
        quote_quantity=str(tick.quote_quantity),
        traded_at=tick.traded_at,
        is_buyer_maker=tick.is_buyer_maker,
    )


def persisted_order_book_to_response(snapshot: OrderBookSnapshot) -> PersistedOrderBookResponse:
    return PersistedOrderBookResponse(
        symbol=snapshot.symbol,
        last_update_id=snapshot.last_update_id,
        bids=[
            PersistedOrderBookLevelResponse(price=str(level.price), quantity=str(level.quantity))
            for level in snapshot.bids
        ],
        asks=[
            PersistedOrderBookLevelResponse(price=str(level.price), quantity=str(level.quantity))
            for level in snapshot.asks
        ],
        retrieved_at=snapshot.retrieved_at,
    )
