"""`RiskAssessment`: the result `RiskEngine.evaluate` hands back for a single
order — never persisted, just returned up the call stack (and, on
rejection, folded into the `reason` recorded on the `Order`/`Signal`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    approved: bool
    risk_score: Decimal
    reasons: list[str] = field(default_factory=list)
    recommended_stop_loss: Decimal | None = None
    recommended_take_profit: Decimal | None = None

    @property
    def reason_text(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""
