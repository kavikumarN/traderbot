"""Risk-engine domain exceptions — subclass the shared `DomainError` so the
existing HTTP exception-handler pipeline (`app.interface.api.errors`) picks
them up automatically, same as `app.domain.trading.exceptions`.

Three distinct failure modes, each with its own recovery path: a rule
breach is per-order and clears on the next signal (`RiskLimitExceededError`);
a tripped circuit breaker is account-wide and self-heals after its cooldown
(`CircuitBreakerTrippedError`); an emergency stop is account-wide and stays
active until a human clears it (`EmergencyStopActiveError`).
"""

from __future__ import annotations

from datetime import datetime

from app.domain.exceptions import DomainError


class RiskLimitExceededError(DomainError):
    """`RiskEngine.evaluate` rejected an order against one or more active
    `RiskRule`s (or the composite risk score gate). `reasons` holds one
    human-readable line per violated rule, in evaluation order."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons) if reasons else "Risk limit exceeded")


class CircuitBreakerTrippedError(DomainError):
    """The account's automatic circuit breaker is `OPEN` — some combination
    of daily loss, drawdown, or consecutive-loss limits was breached and
    every new order is blocked until `resume_at` (or a manual reset)."""

    def __init__(self, reason: str, resume_at: datetime | None) -> None:
        self.reason = reason
        self.resume_at = resume_at
        suffix = f", resumes at {resume_at.isoformat()}" if resume_at else ""
        super().__init__(f"Circuit breaker is open: {reason}{suffix}")


class EmergencyStopActiveError(DomainError):
    """A human (or an admin action) explicitly halted this account's
    trading. Unlike the circuit breaker, this never auto-resumes."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Emergency stop is active: {reason}")
