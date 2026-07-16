"""Exchange-agnostic enums.

Values are kept identical to Binance's own wire vocabulary (`BUY`, `LIMIT`,
`1m`, ...) so mapping in `infrastructure/binance/mappers.py` is a plain
`Enum(value)` call — but the *types* live in the domain because "an order
has a side" is a business concept, not a Binance one.
"""

from __future__ import annotations

from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class OrderStatus(StrEnum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PENDING_CANCEL = "PENDING_CANCEL"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class TimeInForce(StrEnum):
    GTC = "GTC"  # Good 'Til Canceled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class KlineInterval(StrEnum):
    ONE_MINUTE = "1m"
    THREE_MINUTES = "3m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    SIX_HOURS = "6h"
    EIGHT_HOURS = "8h"
    TWELVE_HOURS = "12h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "1w"
    ONE_MONTH = "1M"


class SymbolStatus(StrEnum):
    TRADING = "TRADING"
    BREAK = "BREAK"
    HALT = "HALT"
    AUCTION_MATCH = "AUCTION_MATCH"
    PRE_TRADING = "PRE_TRADING"
    POST_TRADING = "POST_TRADING"


class ConnectionState(StrEnum):
    """Lifecycle of a streaming (WebSocket) connection — surfaced to
    consumers so a UI/monitoring layer can show "reconnecting" instead of
    silently going stale."""

    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    CLOSED = "CLOSED"
