from __future__ import annotations

from app.domain.strategy.pattern_recognition import (
    IntervalAnalysis,
    PatternAnalysisResult,
    PatternMatch,
    StrategySuggestion,
)
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


def interval_analysis_to_response(analysis: IntervalAnalysis) -> IntervalAnalysisResponse:
    return IntervalAnalysisResponse(
        interval=analysis.interval.value,
        candle_count=analysis.candle_count,
        patterns=[pattern_match_to_response(p) for p in analysis.patterns],
    )


def suggestion_to_response(suggestion: StrategySuggestion) -> StrategySuggestionResponse:
    return StrategySuggestionResponse(
        strategy_type=suggestion.strategy_type,
        parameters=suggestion.parameters,
        bucket=suggestion.bucket.value,
        confidence=str(suggestion.confidence),
        rationale=suggestion.rationale,
    )


def analysis_result_to_response(result: PatternAnalysisResult) -> PatternAnalysisResponse:
    return PatternAnalysisResponse(
        symbol=result.symbol,
        intervals=[interval_analysis_to_response(a) for a in result.intervals],
        suggestion=suggestion_to_response(result.suggestion) if result.suggestion is not None else None,
    )
