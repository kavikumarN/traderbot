"""Domain exchange model -> API response mapping."""

from __future__ import annotations

from app.domain.exchange.models.exchange_info import ExchangeInfo, SymbolInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker
from app.interface.api.schemas.market import (
    CandleResponse,
    ExchangeInfoResponse,
    OrderBookLevelResponse,
    OrderBookResponse,
    SymbolInfoResponse,
    TickerResponse,
)


def symbol_info_to_response(info: SymbolInfo) -> SymbolInfoResponse:
    return SymbolInfoResponse(
        symbol=info.symbol,
        base_asset=info.base_asset,
        quote_asset=info.quote_asset,
        status=info.status.value,
        tick_size=str(info.price_filter.tick_size) if info.price_filter else None,
        step_size=str(info.lot_size_filter.step_size) if info.lot_size_filter else None,
        min_notional=str(info.notional_filter.min_notional) if info.notional_filter else None,
    )


def exchange_info_to_response(info: ExchangeInfo) -> ExchangeInfoResponse:
    return ExchangeInfoResponse(
        server_time=info.server_time,
        symbol_count=len(info.symbols),
        symbols=[symbol_info_to_response(symbol) for symbol in info.symbols],
    )


def ticker_to_response(ticker: Ticker) -> TickerResponse:
    return TickerResponse(
        symbol=ticker.symbol,
        last_price=str(ticker.last_price),
        bid_price=str(ticker.bid_price),
        ask_price=str(ticker.ask_price),
        high_price=str(ticker.high_price),
        low_price=str(ticker.low_price),
        volume=str(ticker.volume),
        quote_volume=str(ticker.quote_volume),
        price_change_percent=str(ticker.price_change_percent),
        open_time=ticker.open_time,
        close_time=ticker.close_time,
    )


def order_book_to_response(book: OrderBookSnapshot) -> OrderBookResponse:
    return OrderBookResponse(
        symbol=book.symbol,
        last_update_id=book.last_update_id,
        bids=[OrderBookLevelResponse(price=str(level.price), quantity=str(level.quantity)) for level in book.bids],
        asks=[OrderBookLevelResponse(price=str(level.price), quantity=str(level.quantity)) for level in book.asks],
    )


def candle_to_response(candle: Candle) -> CandleResponse:
    return CandleResponse(
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
        is_closed=candle.is_closed,
    )
