"""The "AI Strategy Builder": fetches recent candles for a symbol across
whichever intervals the caller asks for, runs them through
`app.domain.strategy.pattern_recognition`, and returns the raw per-interval
pattern matches, the aggregated strategy suggestion, and the candles
themselves (so a caller can chart exactly the data the patterns were
detected against) — all read-only, no persistence (there's no strategy to
save until the user accepts the suggestion and calls `CreateStrategyUseCase`
themselves).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.exceptions import ValidationError
from app.domain.exchange.enums import KlineInterval
from app.domain.exchange.models.market_data import Candle
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.domain.strategy.pattern_recognition import PatternAnalysisResult, build_analysis_result

_CANDLES_PER_INTERVAL = 200
_MAX_INTERVALS = 5


@dataclass(frozen=True, slots=True)
class AnalyzePatternsCommand:
    symbol: str
    intervals: list[KlineInterval]


@dataclass(frozen=True, slots=True)
class AnalyzePatternsOutput:
    analysis: PatternAnalysisResult
    candles_by_interval: dict[KlineInterval, list[Candle]]


class AnalyzePatternsUseCase:
    def __init__(self, market_data: IMarketDataReader) -> None:
        self._market_data = market_data

    async def execute(self, command: AnalyzePatternsCommand) -> AnalyzePatternsOutput:
        if not command.intervals:
            raise ValidationError("At least one interval is required")
        if len(command.intervals) > _MAX_INTERVALS:
            raise ValidationError(f"At most {_MAX_INTERVALS} intervals may be analyzed at once")

        per_interval = []
        for interval in command.intervals:
            candles = await self._market_data.get_candles(command.symbol, interval, limit=_CANDLES_PER_INTERVAL)
            per_interval.append((interval, candles))

        if all(not candles for _, candles in per_interval):
            raise ValidationError(f"No candle data available for {command.symbol}")

        analysis = build_analysis_result(command.symbol, per_interval)
        return AnalyzePatternsOutput(
            analysis=analysis, candles_by_interval={interval: candles for interval, candles in per_interval}
        )
