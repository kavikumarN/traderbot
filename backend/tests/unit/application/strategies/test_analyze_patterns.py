from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.application.use_cases.strategies.analyze_patterns import AnalyzePatternsCommand, AnalyzePatternsUseCase
from app.domain.exceptions import ValidationError
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from tests.fakes.fake_exchange_client import FakeExchangeClient

pytestmark = pytest.mark.asyncio

_SYMBOL = "BTCUSDT"


def _candles(count: int = 40) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        Candle(
            symbol=_SYMBOL,
            interval=KlineInterval.ONE_HOUR,
            open_time=start + timedelta(hours=i),
            close_time=start + timedelta(hours=i + 1),
            open=Decimal(100),
            high=Decimal("100.5"),
            low=Decimal("99.5"),
            close=Decimal(100),
            volume=Decimal(10),
            quote_volume=Decimal(1000),
            trade_count=5,
            is_closed=True,
        )
        for i in range(count)
    ]


async def test_analyzes_a_single_interval() -> None:
    exchange = FakeExchangeClient()
    exchange.candles_result = _candles()
    use_case = AnalyzePatternsUseCase(exchange)

    result = await use_case.execute(AnalyzePatternsCommand(symbol=_SYMBOL, intervals=[KlineInterval.ONE_HOUR]))

    assert result.symbol == _SYMBOL
    assert len(result.intervals) == 1
    assert result.intervals[0].interval == KlineInterval.ONE_HOUR
    assert result.intervals[0].candle_count == 40


async def test_analyzes_multiple_intervals() -> None:
    exchange = FakeExchangeClient()
    exchange.candles_result = _candles()
    use_case = AnalyzePatternsUseCase(exchange)

    result = await use_case.execute(
        AnalyzePatternsCommand(symbol=_SYMBOL, intervals=[KlineInterval.ONE_HOUR, KlineInterval.ONE_DAY])
    )

    assert len(result.intervals) == 2
    assert {a.interval for a in result.intervals} == {KlineInterval.ONE_HOUR, KlineInterval.ONE_DAY}


async def test_rejects_empty_interval_list() -> None:
    use_case = AnalyzePatternsUseCase(FakeExchangeClient())
    with pytest.raises(ValidationError):
        await use_case.execute(AnalyzePatternsCommand(symbol=_SYMBOL, intervals=[]))


async def test_rejects_too_many_intervals() -> None:
    use_case = AnalyzePatternsUseCase(FakeExchangeClient())
    intervals = [
        KlineInterval.ONE_MINUTE,
        KlineInterval.FIVE_MINUTES,
        KlineInterval.FIFTEEN_MINUTES,
        KlineInterval.ONE_HOUR,
        KlineInterval.FOUR_HOURS,
        KlineInterval.ONE_DAY,
    ]
    with pytest.raises(ValidationError):
        await use_case.execute(AnalyzePatternsCommand(symbol=_SYMBOL, intervals=intervals))


async def test_rejects_when_no_candle_data_available() -> None:
    exchange = FakeExchangeClient()
    exchange.candles_result = []
    use_case = AnalyzePatternsUseCase(exchange)
    with pytest.raises(ValidationError):
        await use_case.execute(AnalyzePatternsCommand(symbol=_SYMBOL, intervals=[KlineInterval.ONE_HOUR]))
