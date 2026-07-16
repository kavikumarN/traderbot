from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.services.market_data_service import MarketDataService
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle, OrderBookLevel, OrderBookSnapshot, Ticker, Trade
from tests.fakes.fake_market_data_repository import FakeBroadcaster, FakeMarketDataRepository
from tests.fakes.fake_market_data_stream import BLOCK, FakeMarketDataStream


def make_candle(**overrides: object) -> Candle:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        interval=KlineInterval.ONE_MINUTE,
        open_time=now,
        close_time=now,
        open=Decimal("1"),
        high=Decimal("2"),
        low=Decimal("0.5"),
        close=Decimal("1.5"),
        volume=Decimal("100"),
        quote_volume=Decimal("150"),
        trade_count=5,
        is_closed=False,
    )
    defaults.update(overrides)
    return Candle(**defaults)  # type: ignore[arg-type]


def make_trade(**overrides: object) -> Trade:
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        trade_id=1,
        price=Decimal("100"),
        quantity=Decimal("1"),
        quote_quantity=Decimal("100"),
        traded_at=datetime.now(UTC),
        is_buyer_maker=False,
    )
    defaults.update(overrides)
    return Trade(**defaults)  # type: ignore[arg-type]


def make_order_book(**overrides: object) -> OrderBookSnapshot:
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        last_update_id=1,
        bids=(OrderBookLevel(price=Decimal("99"), quantity=Decimal("1")),),
        asks=(OrderBookLevel(price=Decimal("101"), quantity=Decimal("1")),),
        retrieved_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return OrderBookSnapshot(**defaults)  # type: ignore[arg-type]


def make_ticker(**overrides: object) -> Ticker:
    now = datetime.now(UTC)
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        last_price=Decimal("100"),
        bid_price=Decimal("99"),
        ask_price=Decimal("101"),
        high_price=Decimal("105"),
        low_price=Decimal("95"),
        volume=Decimal("1000"),
        quote_volume=Decimal("100000"),
        price_change_percent=Decimal("1.5"),
        open_time=now,
        close_time=now,
    )
    defaults.update(overrides)
    return Ticker(**defaults)  # type: ignore[arg-type]


def make_service(
    stream: FakeMarketDataStream,
    repository: FakeMarketDataRepository,
    broadcaster: FakeBroadcaster,
    *,
    symbols: list[str] | None = None,
) -> MarketDataService:
    return MarketDataService(
        stream,
        repository,
        broadcaster,
        symbols=symbols or ["BTCUSDT"],
        candle_intervals=[KlineInterval.ONE_MINUTE],
    )


@pytest.mark.asyncio
async def test_start_persists_and_broadcasts_every_channel() -> None:
    stream = FakeMarketDataStream()
    stream.trades["BTCUSDT"] = [make_trade(trade_id=1)]
    stream.tickers["BTCUSDT"] = [make_ticker()]
    stream.order_books["BTCUSDT"] = [make_order_book()]
    stream.candles[("BTCUSDT", KlineInterval.ONE_MINUTE)] = [make_candle()]

    repository = FakeMarketDataRepository()
    broadcaster = FakeBroadcaster()
    service = make_service(stream, repository, broadcaster)

    await service.start()
    await asyncio.gather(*service._tasks)  # scripted streams are finite — wait for them to drain

    assert len(repository.saved_trades) == 1
    assert len(repository.saved_volume_stats) == 1
    assert len(repository.saved_order_books) == 1
    assert len(repository.saved_candles) == 1

    channels_broadcast = {message["channel"] for _symbol, message in broadcaster.messages}
    assert channels_broadcast == {"trade", "ticker", "orderbook", "candle"}
    assert all(symbol == "BTCUSDT" for symbol, _message in broadcaster.messages)


@pytest.mark.asyncio
async def test_start_twice_raises() -> None:
    stream = FakeMarketDataStream()
    service = make_service(stream, FakeMarketDataRepository(), FakeBroadcaster())

    await service.start()
    with pytest.raises(RuntimeError):
        await service.start()

    await service.stop()


@pytest.mark.asyncio
async def test_error_handling_one_message_does_not_stop_the_stream() -> None:
    stream = FakeMarketDataStream()
    good = make_candle(close=Decimal("2"))
    bad = make_candle(close=Decimal("3"))
    stream.candles[("BTCUSDT", KlineInterval.ONE_MINUTE)] = [bad, good]

    repository = FakeMarketDataRepository()
    seen: list[Candle] = []

    def blow_up_once(candle: Candle) -> None:
        seen.append(candle)
        if candle is bad:
            raise ValueError("boom")

    repository.candle_side_effect = blow_up_once
    broadcaster = FakeBroadcaster()
    service = make_service(stream, repository, broadcaster)

    await service.start()
    await asyncio.gather(*service._tasks)

    # Both messages were handed to the repository (the failure didn't stop
    # iteration)...
    assert seen == [bad, good]
    # ...but only the one that didn't raise was actually persisted/broadcast.
    assert repository.saved_candles == [good]
    assert len(broadcaster.messages) == 1


@pytest.mark.asyncio
async def test_stop_cancels_running_tasks_and_closes_the_stream() -> None:
    stream = FakeMarketDataStream()
    stream.trades["BTCUSDT"] = [BLOCK]  # never completes on its own
    service = make_service(stream, FakeMarketDataRepository(), FakeBroadcaster())

    await service.start()
    assert service.running is True

    await service.stop()

    assert stream.closed is True
    assert service.running is False


@pytest.mark.asyncio
async def test_stop_without_start_is_a_safe_no_op() -> None:
    stream = FakeMarketDataStream()
    service = make_service(stream, FakeMarketDataRepository(), FakeBroadcaster())

    await service.stop()

    assert stream.closed is False
