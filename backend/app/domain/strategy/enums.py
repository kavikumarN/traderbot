from __future__ import annotations

from enum import StrEnum


class StrategyStatus(StrEnum):
    """Mirrors Phase 0's strategy-lifecycle state diagram: a strategy earns
    its way to live capital through validation, backtesting, and paper
    trading before a human promotes it."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    BACKTESTING = "BACKTESTING"
    PAPER_TRADING = "PAPER_TRADING"
    LIVE = "LIVE"
    PAUSED = "PAUSED"
    REJECTED = "REJECTED"
    RETIRED = "RETIRED"


class SignalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


class BacktestStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
