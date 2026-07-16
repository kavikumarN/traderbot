"""Read-only market data — proves the Binance integration is wired end to
end through the same DI/composition-root pattern as every other route.

Requires an authenticated session (this is a logged-in product, not a
public API) but no specific permission — there's no meaningful way to
restrict "can view the ticker" independent of "can use the platform at all".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.interface.api.deps import get_current_access_token_payload, get_market_data_reader
from app.interface.api.exchange_mappers import (
    candle_to_response,
    exchange_info_to_response,
    order_book_to_response,
    ticker_to_response,
)
from app.interface.api.schemas.market import (
    CandleResponse,
    ExchangeInfoResponse,
    OrderBookResponse,
    TickerResponse,
)

router = APIRouter(
    prefix="/market",
    tags=["market"],
    dependencies=[Depends(get_current_access_token_payload)],
)


@router.get("/exchange-info", response_model=ExchangeInfoResponse, summary="Symbol catalog and trading rules")
async def get_exchange_info(
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> ExchangeInfoResponse:
    info = await market_data.get_exchange_info()
    return exchange_info_to_response(info)


@router.get("/ticker/{symbol}", response_model=TickerResponse, summary="24h ticker statistics")
async def get_ticker(
    symbol: str, market_data: IMarketDataReader = Depends(get_market_data_reader)
) -> TickerResponse:
    ticker = await market_data.get_ticker(symbol)
    return ticker_to_response(ticker)


@router.get("/orderbook/{symbol}", response_model=OrderBookResponse, summary="Order book snapshot")
async def get_order_book(
    symbol: str,
    limit: int = Query(default=100, ge=5, le=5000),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> OrderBookResponse:
    book = await market_data.get_order_book(symbol, limit=limit)
    return order_book_to_response(book)


@router.get("/candles/{symbol}", response_model=list[CandleResponse], summary="Historical candles (klines)")
async def get_candles(
    symbol: str,
    interval: KlineInterval = Query(default=KlineInterval.ONE_HOUR),
    limit: int = Query(default=500, ge=1, le=1000),
    market_data: IMarketDataReader = Depends(get_market_data_reader),
) -> list[CandleResponse]:
    candles = await market_data.get_candles(symbol, interval, limit=limit)
    return [candle_to_response(candle) for candle in candles]
