"""Simulated `ExchangeClient` for paper trading.

Market data is real — `IMarketDataReader` calls are delegated to whatever
the process is really using for prices (Binance's public REST endpoints,
which need no API key), so fills happen against live prices. `IOrderPlacer`
and `IAccountReader`, however, are backed entirely by an in-memory
simulator: no order placed through this adapter ever reaches an exchange.

Deliberate simplifications (this is a paper-trading simulator, not a
matching-engine clone):

* Resting limit/stop orders are matched *lazily* — re-evaluated against the
  current price only when `get_order` / `cancel_order` / `get_open_orders`
  is called, not continuously. `ExecutionService`'s reconciliation path is
  what drives this in practice, exactly as it would poll a real exchange.
* Balance is not reserved when a resting order is placed, only checked and
  moved at actual fill time. Real exchanges lock funds immediately;
  duplicating that here would mean building a real margin engine for a
  feature whose entire point is *not* being a real exchange.
* Orders live in memory only — a process restart loses resting paper
  orders. Anything already filled is unaffected, since `ExecutionService`
  persists fills as platform `Order`/`Trade` rows immediately.
* One flat commission rate applies to both sides, taken from the asset
  received (base on a buy, quote on a sell) — matching Binance's default
  (non-BNB-discounted) spot fee.
"""

from __future__ import annotations

import asyncio
import itertools
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.exchange.enums import KlineInterval, OrderSide, OrderStatus, OrderType
from app.domain.exchange.exceptions import InsufficientBalanceError, OrderNotFoundError, OrderRejectedError
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.exchange.models.exchange_info import ExchangeInfo
from app.domain.exchange.models.market_data import Candle, OrderBookSnapshot, Ticker, Trade
from app.domain.exchange.models.requests import PlaceOrderRequest
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.exchange.ports.market_data_reader import IMarketDataReader

DEFAULT_COMMISSION_RATE = Decimal("0.001")  # 0.1%, Binance's standard spot taker/maker fee
DEFAULT_STARTING_BALANCES: dict[str, Decimal] = {"USDT": Decimal("100000")}
_KNOWN_QUOTE_ASSETS = ("USDT", "BUSD", "USDC", "FDUSD", "TUSD", "BTC", "ETH", "BNB")

_STOP_LOSS_TYPES = frozenset({OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT})
_TAKE_PROFIT_TYPES = frozenset({OrderType.TAKE_PROFIT, OrderType.TAKE_PROFIT_LIMIT})
_STOP_TYPES = _STOP_LOSS_TYPES | _TAKE_PROFIT_TYPES
_TRIGGER_THEN_MARKET_TYPES = frozenset({OrderType.STOP_LOSS, OrderType.TAKE_PROFIT})
_LIMIT_STAGE_TYPES = frozenset(
    {OrderType.LIMIT, OrderType.LIMIT_MAKER, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT}
)


def _split_symbol(symbol: str) -> tuple[str, str]:
    symbol = symbol.upper()
    for quote in _KNOWN_QUOTE_ASSETS:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[: -len(quote)], quote
    raise OrderRejectedError(f"Cannot determine base/quote assets for symbol {symbol}")


class PaperTradingExchangeAdapter(ExchangeClient):
    def __init__(
        self,
        market_data: IMarketDataReader,
        *,
        starting_balances: dict[str, Decimal] | None = None,
        commission_rate: Decimal = DEFAULT_COMMISSION_RATE,
    ) -> None:
        self._market_data = market_data
        self._commission_rate = commission_rate
        self._balances: dict[str, AssetBalance] = {
            asset: AssetBalance(asset=asset, free=amount, locked=Decimal(0))
            for asset, amount in (starting_balances or DEFAULT_STARTING_BALANCES).items()
        }
        self._orders: dict[int, ExchangeOrder] = {}
        self._orders_by_client_id: dict[str, int] = {}
        self._triggered: set[int] = set()
        self._id_seq = itertools.count(1)
        self._lock = asyncio.Lock()

    # --- IMarketDataReader passthrough: paper trading still needs real prices ---

    async def get_exchange_info(self) -> ExchangeInfo:
        return await self._market_data.get_exchange_info()

    async def get_ticker(self, symbol: str) -> Ticker:
        return await self._market_data.get_ticker(symbol)

    async def get_order_book(self, symbol: str, *, limit: int = 100) -> OrderBookSnapshot:
        return await self._market_data.get_order_book(symbol, limit=limit)

    async def get_candles(
        self,
        symbol: str,
        interval: KlineInterval,
        *,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Candle]:
        return await self._market_data.get_candles(
            symbol, interval, limit=limit, start_time=start_time, end_time=end_time
        )

    async def get_recent_trades(self, symbol: str, *, limit: int = 500) -> list[Trade]:
        return await self._market_data.get_recent_trades(symbol, limit=limit)

    # --- IAccountReader ---

    async def get_balances(self) -> list[AssetBalance]:
        async with self._lock:
            return list(self._balances.values())

    # --- IOrderPlacer ---

    async def place_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        ticker = await self._market_data.get_ticker(request.symbol)
        now = datetime.now(UTC)

        async with self._lock:
            exchange_order_id = next(self._id_seq)
            client_order_id = request.client_order_id or f"paper-{exchange_order_id}"
            if client_order_id in self._orders_by_client_id:
                raise OrderRejectedError(f"Duplicate client_order_id {client_order_id}")

            order = ExchangeOrder(
                symbol=request.symbol.upper(),
                exchange_order_id=exchange_order_id,
                client_order_id=client_order_id,
                side=request.side,
                type=request.type,
                status=OrderStatus.NEW,
                time_in_force=request.time_in_force,
                price=request.price or Decimal(0),
                original_quantity=request.quantity,
                executed_quantity=Decimal(0),
                cumulative_quote_quantity=Decimal(0),
                created_at=now,
                updated_at=now,
                stop_price=request.stop_price,
            )
            self._orders_by_client_id[client_order_id] = exchange_order_id
            order = self._try_fill(order, ticker)
            self._orders[exchange_order_id] = order
            return order

    async def cancel_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        async with self._lock:
            order = self._find(symbol, exchange_order_id, client_order_id)
            if order.is_terminal:
                raise OrderRejectedError(f"Order {order.exchange_order_id} is already {order.status.value}")
            cancelled = _with_status(order, OrderStatus.CANCELED)
            self._orders[order.exchange_order_id] = cancelled
            return cancelled

    async def get_order(
        self,
        symbol: str,
        *,
        exchange_order_id: int | None = None,
        client_order_id: str | None = None,
    ) -> ExchangeOrder:
        ticker = await self._market_data.get_ticker(symbol)
        async with self._lock:
            order = self._find(symbol, exchange_order_id, client_order_id)
            if not order.is_terminal:
                order = self._try_fill(order, ticker)
                self._orders[order.exchange_order_id] = order
            return order

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        async with self._lock:
            candidate_ids = [
                order.exchange_order_id
                for order in self._orders.values()
                if not order.is_terminal and (symbol is None or order.symbol == symbol.upper())
            ]

        still_open: list[ExchangeOrder] = []
        for order_id in candidate_ids:
            async with self._lock:
                current = self._orders.get(order_id)
            if current is None or current.is_terminal:
                continue
            ticker = await self._market_data.get_ticker(current.symbol)
            async with self._lock:
                current = self._orders.get(order_id)
                if current is None or current.is_terminal:
                    continue
                updated = self._try_fill(current, ticker)
                self._orders[order_id] = updated
                if not updated.is_terminal:
                    still_open.append(updated)
        return still_open

    # --- internal matching (all of `_find`/`_try_fill`/`_fill` assume the caller holds `self._lock`) ---

    def _find(self, symbol: str, exchange_order_id: int | None, client_order_id: str | None) -> ExchangeOrder:
        if exchange_order_id is not None:
            order = self._orders.get(exchange_order_id)
        elif client_order_id is not None:
            internal_id = self._orders_by_client_id.get(client_order_id)
            order = self._orders.get(internal_id) if internal_id is not None else None
        else:
            raise ValueError("Provide either exchange_order_id or client_order_id")

        if order is None or order.symbol != symbol.upper():
            raise OrderNotFoundError(f"No such order for {symbol}")
        return order

    def _try_fill(self, order: ExchangeOrder, ticker: Ticker) -> ExchangeOrder:
        if order.type in _STOP_TYPES and order.exchange_order_id not in self._triggered:
            if not _stop_triggered(order.type, order.side, order.stop_price, ticker.last_price):
                return order
            self._triggered.add(order.exchange_order_id)
            if order.type in _TRIGGER_THEN_MARKET_TYPES:
                return self._fill(order, _market_fill_price(order.side, ticker))

        if order.type in _LIMIT_STAGE_TYPES:
            if _limit_marketable(order.side, order.price, ticker):
                return self._fill(order, order.price)
            return order

        return self._fill(order, _market_fill_price(order.side, ticker))

    def _fill(self, order: ExchangeOrder, fill_price: Decimal) -> ExchangeOrder:
        notional = fill_price * order.original_quantity
        base_asset, quote_asset = _split_symbol(order.symbol)

        if order.side == OrderSide.BUY:
            commission = order.original_quantity * self._commission_rate
            self._debit(quote_asset, notional)
            self._credit(base_asset, order.original_quantity - commission)
        else:
            commission = notional * self._commission_rate
            self._debit(base_asset, order.original_quantity)
            self._credit(quote_asset, notional - commission)

        return ExchangeOrder(
            symbol=order.symbol,
            exchange_order_id=order.exchange_order_id,
            client_order_id=order.client_order_id,
            side=order.side,
            type=order.type,
            status=OrderStatus.FILLED,
            time_in_force=order.time_in_force,
            price=order.price if order.price else fill_price,
            original_quantity=order.original_quantity,
            executed_quantity=order.original_quantity,
            cumulative_quote_quantity=notional,
            created_at=order.created_at,
            updated_at=datetime.now(UTC),
            stop_price=order.stop_price,
        )

    def _debit(self, asset: str, amount: Decimal) -> None:
        balance = self._balances.get(asset, AssetBalance(asset=asset, free=Decimal(0), locked=Decimal(0)))
        if balance.free < amount:
            raise InsufficientBalanceError(f"Insufficient {asset}: need {amount}, have {balance.free}")
        self._balances[asset] = AssetBalance(asset=asset, free=balance.free - amount, locked=balance.locked)

    def _credit(self, asset: str, amount: Decimal) -> None:
        balance = self._balances.get(asset, AssetBalance(asset=asset, free=Decimal(0), locked=Decimal(0)))
        self._balances[asset] = AssetBalance(asset=asset, free=balance.free + amount, locked=balance.locked)


def _with_status(order: ExchangeOrder, status: OrderStatus) -> ExchangeOrder:
    return ExchangeOrder(
        symbol=order.symbol,
        exchange_order_id=order.exchange_order_id,
        client_order_id=order.client_order_id,
        side=order.side,
        type=order.type,
        status=status,
        time_in_force=order.time_in_force,
        price=order.price,
        original_quantity=order.original_quantity,
        executed_quantity=order.executed_quantity,
        cumulative_quote_quantity=order.cumulative_quote_quantity,
        created_at=order.created_at,
        updated_at=datetime.now(UTC),
        stop_price=order.stop_price,
    )


def _market_fill_price(side: OrderSide, ticker: Ticker) -> Decimal:
    return ticker.ask_price if side == OrderSide.BUY else ticker.bid_price


def _limit_marketable(side: OrderSide, limit_price: Decimal, ticker: Ticker) -> bool:
    return ticker.ask_price <= limit_price if side == OrderSide.BUY else ticker.bid_price >= limit_price


def _stop_triggered(
    order_type: OrderType, side: OrderSide, stop_price: Decimal | None, last_price: Decimal
) -> bool:
    if stop_price is None:
        return False
    if order_type in _STOP_LOSS_TYPES:
        return last_price <= stop_price if side == OrderSide.SELL else last_price >= stop_price
    return last_price >= stop_price if side == OrderSide.SELL else last_price <= stop_price
