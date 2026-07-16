from __future__ import annotations

from app.application.use_cases.strategies.analyze_patterns import AnalyzePatternsOutput
from app.domain.exchange.models.market_data import Candle
from app.domain.strategy.pattern_recognition import IntervalAnalysis, PatternMatch, StrategySuggestion
from app.interface.api.exchange_mappers import candle_to_response
from app.interface.api.schemas.pattern_analysis import (
    IntervalAnalysisResponse,
    PatternAnalysisResponse,
    PatternMatchResponse,
    StrategySuggestionResponse,
)


def pattern_match_to_response(match: PatternMatch) -> PatternMatchResponse:
    return PatternMatchResponse(
        name=match.name,
        signal=match.signal.value,
        bucket=match.bucket.value,
        at=match.at,
        confidence=str(match.confidence),
        description=match.description,
    )


def interval_analysis_to_response(analysis: IntervalAnalysis, candles: list[Candle]) -> IntervalAnalysisResponse:
    return IntervalAnalysisResponse(
        interval=analysis.interval.value,
        candle_count=analysis.candle_count,
        patterns=[pattern_match_to_response(p) for p in analysis.patterns],
        candles=[candle_to_response(c) for c in candles],
    )


def suggestion_to_response(suggestion: StrategySuggestion) -> StrategySuggestionResponse:
    return StrategySuggestionResponse(
        strategy_type=suggestion.strategy_type,
        parameters=suggestion.parameters,
        bucket=suggestion.bucket.value,
        confidence=str(suggestion.confidence),
        rationale=suggestion.rationale,
    )


def analyze_patterns_output_to_response(output: AnalyzePatternsOutput) -> PatternAnalysisResponse:
    result = output.analysis
    return PatternAnalysisResponse(
        symbol=result.symbol,
        intervals=[
            interval_analysis_to_response(a, output.candles_by_interval.get(a.interval, [])) for a in result.intervals
        ],
        suggestion=suggestion_to_response(result.suggestion) if result.suggestion is not None else None,
    )
