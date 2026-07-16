"""Request/response models for the AI Strategy Builder's pattern-analysis
endpoint (`POST /strategies/ai-builder/analyze`). Same string-serialization
convention as `schemas/strategy.py` for anything Decimal-valued.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.exchange.enums import KlineInterval
from app.interface.api.schemas.market import CandleResponse


class AnalyzePatternsRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    intervals: list[KlineInterval] = Field(min_length=1, max_length=5)


class PatternMatchResponse(BaseModel):
    name: str
    signal: str
    bucket: str
    at: datetime
    confidence: str
    description: str


class IntervalAnalysisResponse(BaseModel):
    interval: str
    candle_count: int
    patterns: list[PatternMatchResponse]
    candles: list[CandleResponse]


class StrategySuggestionResponse(BaseModel):
    strategy_type: str
    parameters: dict[str, Any]
    bucket: str
    confidence: str
    rationale: str


class PatternAnalysisResponse(BaseModel):
    symbol: str
    intervals: list[IntervalAnalysisResponse]
    suggestion: StrategySuggestionResponse | None
