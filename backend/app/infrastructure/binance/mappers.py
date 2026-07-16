"""Anti-corruption layer: translates raw Binance JSON into domain models.

This is the *only* module allowed to know Binance's field names
(`cummulativeQuoteQty`, double-m typo and all) or its quirks (numbers sent
as strings, timestamps in epoch milliseconds, two different spellings of
the notional filter across API versions). Everything past this module
speaks the domain's vocabulary exclusively.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.exchange.enums import (
    KlineInterval,
    OrderSide,
    OrderStatus,
    OrderType,
    SymbolStatus,
    TimeInForce,
)
from app.domain.exchange.exceptions import ExchangeError
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.exchange.models.exchange_info import (
    ExchangeInfo,
    LotSizeFilter,
    NotionalFilter,
    PriceFilter,
    SymbolInfo,
)
from app.domain.exchange.models.market_data import (
    Candle,
    OrderBookLevel,
    OrderBookSnapshot,
    Ticker,
    Trade,
)


def parse_decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ExchangeError(f"Binance returned a non-numeric value: {value!r}") from exc


def parse_timestamp_ms(value: object) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)  # type: ignore[arg-type]


def to_symbol_info(data: dict[str, Any]) -> SymbolInfo:
    filters = {f["filterType"]: f for f in data.get("filters", [])}

    price_filter = None
    if raw := filters.get("PRICE_FILTER"):
        price_filter = PriceFilter(
            min_price=parse_decimal(raw["minPrice"]),
            max_price=parse_decimal(raw["maxPrice"]),
            tick_size=parse_decimal(raw["tickSize"]),
        )

    lot_size_filter = None
    if raw := filters.get("LOT_SIZE"):
        lot_size_filter = LotSizeFilter(
            min_qty=parse_decimal(raw["minQty"]),
            max_qty=parse_decimal(raw["maxQty"]),
            step_size=parse_decimal(raw["stepSize"]),
        )

    # Binance renamed MIN_NOTIONAL -> NOTIONAL; both keys are honored.
    notional_filter = None
    raw = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL")
    if raw:
        min_notional = raw.get("minNotional") or raw.get("notional")
        if min_notional is not None:
            notional_filter = NotionalFilter(min_notional=parse_decimal(min_notional))

    return SymbolInfo(
        symbol=data["symbol"],
        base_asset=data["baseAsset"],
        quote_asset=data["quoteAsset"],
        status=SymbolStatus(data["status"]),
        price_filter=price_filter,
        lot_size_filter=lot_size_filter,
        notional_filter=notional_filter,
    )


def to_exchange_info(data: dict[str, Any]) -> ExchangeInfo:
    return ExchangeInfo(
        server_time=parse_timestamp_ms(data["serverTime"]),
        symbols=tuple(to_symbol_info(entry) for entry in data.get("symbols", [])),
    )


def to_ticker(data: dict[str, Any]) -> Ticker:
    return Ticker(
        symbol=data["symbol"],
        last_price=parse_decimal(data["lastPrice"]),
        bid_price=parse_decimal(data["bidPrice"]),
        ask_price=parse_decimal(data["askPrice"]),
        high_price=parse_decimal(data["highPrice"]),
        low_price=parse_decimal(data["lowPrice"]),
        volume=parse_decimal(data["volume"]),
        quote_volume=parse_decimal(data["quoteVolume"]),
        price_change_percent=parse_decimal(data["priceChangePercent"]),
        open_time=parse_timestamp_ms(data["openTime"]),
        close_time=parse_timestamp_ms(data["closeTime"]),
    )


def to_order_book(symbol: str, data: dict[str, Any]) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        symbol=symbol,
        last_update_id=int(data["lastUpdateId"]),
        bids=tuple(to_order_book_level(level) for level in data.get("bids", [])),
        asks=tuple(to_order_book_level(level) for level in data.get("asks", [])),
        retrieved_at=datetime.now(UTC),
    )


def to_order_book_level(raw: list[str]) -> OrderBookLevel:
    return OrderBookLevel(price=parse_decimal(raw[0]), quantity=parse_decimal(raw[1]))


def to_candle(symbol: str, interval: KlineInterval, raw: list[Any], *, is_closed: bool = True) -> Candle:
    return Candle(
        symbol=symbol,
        interval=interval,
        open_time=parse_timestamp_ms(raw[0]),
        open=parse_decimal(raw[1]),
        high=parse_decimal(raw[2]),
        low=parse_decimal(raw[3]),
        close=parse_decimal(raw[4]),
        volume=parse_decimal(raw[5]),
        close_time=parse_timestamp_ms(raw[6]),
        quote_volume=parse_decimal(raw[7]),
        trade_count=int(raw[8]),
        is_closed=is_closed,
    )


def to_trade(symbol: str, data: dict[str, Any]) -> Trade:
    return Trade(
        symbol=symbol,
        trade_id=int(data["id"]),
        price=parse_decimal(data["price"]),
        quantity=parse_decimal(data["qty"]),
        quote_quantity=parse_decimal(data["quoteQty"]),
        traded_at=parse_timestamp_ms(data["time"]),
        is_buyer_maker=bool(data["isBuyerMaker"]),
    )


def to_asset_balance(data: dict[str, Any]) -> AssetBalance:
    return AssetBalance(
        asset=data["asset"],
        free=parse_decimal(data["free"]),
        locked=parse_decimal(data["locked"]),
    )


def _parse_stop_price(raw: object) -> Decimal | None:
    """Binance always sends `stopPrice`/`P`, using `"0.00000000"` to mean
    "not a stop order" rather than omitting the field — that zero must not
    round-trip as a real stop price."""
    if raw is None:
        return None
    value = parse_decimal(raw)
    return value if value != 0 else None


def to_exchange_order(data: dict[str, Any]) -> ExchangeOrder:
    created_raw = data.get("time") or data.get("transactTime")
    updated_raw = data.get("updateTime") or data.get("transactTime") or created_raw
    time_in_force = data.get("timeInForce")

    return ExchangeOrder(
        symbol=data["symbol"],
        exchange_order_id=int(data["orderId"]),
        client_order_id=data["clientOrderId"],
        side=OrderSide(data["side"]),
        type=OrderType(data["type"]),
        status=OrderStatus(data["status"]),
        time_in_force=TimeInForce(time_in_force) if time_in_force else None,
        price=parse_decimal(data["price"]),
        original_quantity=parse_decimal(data["origQty"]),
        executed_quantity=parse_decimal(data["executedQty"]),
        cumulative_quote_quantity=parse_decimal(
            data.get("cummulativeQuoteQty", data.get("cumulativeQuoteQty", "0"))
        ),
        created_at=parse_timestamp_ms(created_raw) if created_raw else datetime.now(UTC),
        updated_at=parse_timestamp_ms(updated_raw) if updated_raw else datetime.now(UTC),
        stop_price=_parse_stop_price(data.get("stopPrice")),
    )


def to_exchange_order_from_execution_report(data: dict[str, Any]) -> ExchangeOrder:
    """The user-data-stream `executionReport` event uses Binance's other
    convention: single-letter keys instead of the REST API's `camelCase`.
    Same underlying concept, different envelope — still translated here."""
    time_in_force = data.get("f")
    created_raw = data.get("O") or data.get("E")
    updated_raw = data.get("T") or data.get("E")

    return ExchangeOrder(
        symbol=data["s"],
        exchange_order_id=int(data["i"]),
        client_order_id=data["c"],
        side=OrderSide(data["S"]),
        type=OrderType(data["o"]),
        status=OrderStatus(data["X"]),
        time_in_force=TimeInForce(time_in_force) if time_in_force else None,
        price=parse_decimal(data["p"]),
        original_quantity=parse_decimal(data["q"]),
        executed_quantity=parse_decimal(data["z"]),
        cumulative_quote_quantity=parse_decimal(data["Z"]),
        created_at=parse_timestamp_ms(created_raw),
        updated_at=parse_timestamp_ms(updated_raw),
        stop_price=_parse_stop_price(data.get("P")),
    )
