"""Persisted market data (Phase 5) — what `MarketDataService` has actually
stored, plus the live WebSocket broadcast it feeds.

Distinct from `v1/market.py`, which proxies Binance live and touches no
storage. REST reads here require the same login as every other market
route; the WebSocket handshake can't carry an `Authorization` header (browser
`WebSocket` clients can't set arbitrary headers), so the access token is
instead passed as a `?token=` query parameter and verified by hand.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.application.ports.market_data_repository import MarketDataRepository
from app.application.ports.token_blacklist import TokenBlacklist
from app.application.ports.token_service import TokenService
from app.domain.exceptions import InvalidTokenError
from app.domain.exchange.enums import KlineInterval
from app.interface.api.deps import (
    get_current_access_token_payload,
    get_market_data_repository,
    get_token_blacklist,
    get_token_service,
    get_websocket_manager,
)
from app.interface.api.exchange_mappers import ticker_to_response
from app.interface.api.market_data_mappers import (
    market_tick_to_response,
    persisted_candle_to_response,
    persisted_order_book_to_response,
)
from app.interface.api.schemas.market import TickerResponse
from app.interface.api.schemas.market_data import (
    MarketTickResponse,
    PersistedCandleResponse,
    PersistedOrderBookResponse,
)
from app.interface.api.websocket_manager import WebSocketManager

router = APIRouter(
    prefix="/market-data",
    tags=["market-data"],
    dependencies=[Depends(get_current_access_token_payload)],
)


@router.get("/candles/{symbol}", response_model=list[PersistedCandleResponse], summary="Persisted candles")
async def get_persisted_candles(
    symbol: str,
    start: datetime,
    end: datetime,
    interval: KlineInterval = Query(default=KlineInterval.ONE_MINUTE),
    repository: MarketDataRepository = Depends(get_market_data_repository),
) -> list[PersistedCandleResponse]:
    candles = await repository.get_candles(symbol.upper(), interval, start=start, end=end)
    return [persisted_candle_to_response(candle) for candle in candles]


@router.get("/trades/{symbol}", response_model=list[MarketTickResponse], summary="Recent persisted trades")
async def get_persisted_trades(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    repository: MarketDataRepository = Depends(get_market_data_repository),
) -> list[MarketTickResponse]:
    ticks = await repository.get_recent_trades(symbol.upper(), limit=limit)
    return [market_tick_to_response(tick) for tick in ticks]


@router.get(
    "/orderbook/{symbol}", response_model=PersistedOrderBookResponse, summary="Latest persisted order book"
)
async def get_persisted_order_book(
    symbol: str, repository: MarketDataRepository = Depends(get_market_data_repository)
) -> PersistedOrderBookResponse:
    snapshot = await repository.get_order_book(symbol.upper())
    if snapshot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No order book stored yet for {symbol.upper()}")
    return persisted_order_book_to_response(snapshot)


@router.get("/volume/{symbol}", response_model=TickerResponse, summary="Latest 24h volume stats")
async def get_volume_stats(
    symbol: str, repository: MarketDataRepository = Depends(get_market_data_repository)
) -> TickerResponse:
    ticker = await repository.get_volume_stats(symbol.upper())
    if ticker is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No volume stats stored yet for {symbol.upper()}")
    return ticker_to_response(ticker)


@router.websocket("/ws")
async def market_data_websocket(
    websocket: WebSocket,
    manager: WebSocketManager = Depends(get_websocket_manager),
    token_service: TokenService = Depends(get_token_service),
    token_blacklist: TokenBlacklist = Depends(get_token_blacklist),
) -> None:
    """Protocol: connect with `?token=<access token>` and optionally
    `?symbols=BTCUSDT,ETHUSDT` to subscribe immediately. After that, send
    `{"action": "subscribe"|"unsubscribe", "symbols": [...]}` to change
    subscriptions. Every broadcast is `{"channel", "symbol", "data"}` —
    `channel` is one of `candle` | `trade` | `orderbook` | `ticker`.
    """
    token = websocket.query_params.get("token")
    if not token or not await _token_is_valid(token, token_service, token_blacklist):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    initial_symbols = {
        symbol.strip().upper()
        for symbol in websocket.query_params.get("symbols", "").split(",")
        if symbol.strip()
    }
    await manager.connect(websocket, symbols=initial_symbols)
    try:
        while True:
            message = await websocket.receive_json()
            action = message.get("action")
            symbols = {s.upper() for s in message.get("symbols", []) if isinstance(s, str)}
            if not symbols:
                continue
            if action == "subscribe":
                await manager.subscribe(websocket, symbols)
            elif action == "unsubscribe":
                await manager.unsubscribe(websocket, symbols)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


async def _token_is_valid(token: str, token_service: TokenService, token_blacklist: TokenBlacklist) -> bool:
    try:
        payload = token_service.decode_access_token(token)
    except InvalidTokenError:
        return False
    return not await token_blacklist.is_blacklisted(payload.jti)
