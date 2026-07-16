from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.exchange.enums import OrderSide, OrderStatus, OrderType
from app.domain.exchange.models.account import AssetBalance, ExchangeOrder
from app.domain.exchange.models.market_data import OrderBookLevel, OrderBookSnapshot


class TestAssetBalance:
    def test_total_is_free_plus_locked(self) -> None:
        balance = AssetBalance(asset="BTC", free=Decimal("1.5"), locked=Decimal("0.5"))
        assert balance.total == Decimal("2.0")


def make_order(**overrides: object) -> ExchangeOrder:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        exchange_order_id=1,
        client_order_id="abc",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        status=OrderStatus.NEW,
        time_in_force=None,
        price=Decimal("50000"),
        original_quantity=Decimal("1"),
        executed_quantity=Decimal("0.25"),
        cumulative_quote_quantity=Decimal("12500"),
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return ExchangeOrder(**defaults)  # type: ignore[arg-type]


class TestExchangeOrder:
    def test_remaining_quantity(self) -> None:
        order = make_order(original_quantity=Decimal("1"), executed_quantity=Decimal("0.25"))
        assert order.remaining_quantity == Decimal("0.75")

    def test_is_filled(self) -> None:
        assert make_order(status=OrderStatus.FILLED).is_filled is True
        assert make_order(status=OrderStatus.NEW).is_filled is False

    def test_is_terminal(self) -> None:
        for status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED):
            assert make_order(status=status).is_terminal is True
        for status in (OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING_CANCEL):
            assert make_order(status=status).is_terminal is False


class TestOrderBookSnapshot:
    def test_best_bid_and_ask_and_spread(self) -> None:
        book = OrderBookSnapshot(
            symbol="BTCUSDT",
            last_update_id=1,
            bids=(OrderBookLevel(Decimal("100"), Decimal("1")), OrderBookLevel(Decimal("99"), Decimal("2"))),
            asks=(OrderBookLevel(Decimal("101"), Decimal("1")), OrderBookLevel(Decimal("102"), Decimal("2"))),
            retrieved_at=datetime.now(UTC),
        )
        assert book.best_bid == OrderBookLevel(Decimal("100"), Decimal("1"))
        assert book.best_ask == OrderBookLevel(Decimal("101"), Decimal("1"))
        assert book.spread == Decimal("1")

    def test_empty_book_has_no_best_levels_or_spread(self) -> None:
        book = OrderBookSnapshot(
            symbol="BTCUSDT", last_update_id=1, bids=(), asks=(), retrieved_at=datetime.now(UTC)
        )
        assert book.best_bid is None
        assert book.best_ask is None
        assert book.spread is None
