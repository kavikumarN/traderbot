"""Signal Manager: the bridge between the Strategy Engine (Phase 7) and the
trading engine (Phase 6) — turns a plugin's `SignalProposal` into a
persisted, tracked `Signal`, and, when the owning strategy is actually
tradeable, immediately routes it to `TradingService` as a market order.

Approval lifecycle: every signal from a strategy still in
`DRAFT`/`VALIDATED`/`BACKTESTING`/`PAUSED`/etc. is rejected outright here
(those statuses haven't earned the right to move real or paper money,
independent of risk) — everything from a `PAPER_TRADING`/`LIVE` strategy is
approved and routed to `TradingService.place_market_order`, which itself
gates every order through the Risk Engine (Phase 8) before it ever reaches
an exchange. A signal whose order is rejected there (a breached `RiskRule`,
a tripped circuit breaker, an active emergency stop) is caught in
`_execute` below and marked `REJECTED` with that reason, same as an
exchange-side rejection.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.application.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from app.application.services.trading_service import TradingService
from app.domain.exchange.ports.exchange_client import ExchangeClient
from app.domain.risk.exceptions import (
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
    RiskLimitExceededError,
)
from app.domain.strategy.entities import Signal, Strategy
from app.domain.strategy.enums import SignalStatus, StrategyStatus
from app.domain.strategy.plugin import SignalProposal
from app.domain.trading.exceptions import InsufficientBalanceError, OrderRejectedError

_REJECTABLE_EXCEPTIONS = (
    OrderRejectedError,
    InsufficientBalanceError,
    RiskLimitExceededError,
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
)

_TRADEABLE_STATUSES = frozenset({StrategyStatus.PAPER_TRADING, StrategyStatus.LIVE})

# A strategy shouldn't fire two signals on the same side back-to-back —
# guards against a noisy indicator (price oscillating right at a threshold)
# spamming duplicate orders every poll interval. Also used as the default
# signal expiry window.
DEFAULT_COOLDOWN = timedelta(minutes=1)


class SignalManager:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        trading_service: TradingService,
        *,
        cooldown: timedelta = DEFAULT_COOLDOWN,
    ) -> None:
        self._uow_factory = uow_factory
        self._trading_service = trading_service
        self._cooldown = cooldown

    async def submit(
        self,
        strategy: Strategy,
        proposal: SignalProposal,
        *,
        exchange: ExchangeClient,
        auto_execute: bool = True,
    ) -> Signal | None:
        """Persists `proposal` as a `Signal` and, if approved and
        `auto_execute`, places the resulting order. Returns `None` (persists
        nothing) if an equivalent signal already fired within the cooldown
        window."""

        async with self._uow_factory() as uow:
            if await self._is_duplicate(uow, strategy.id, proposal):
                return None

            signal = Signal(
                id=uuid.uuid4(),
                strategy_id=strategy.id,
                symbol=strategy.symbol,
                side=proposal.side,
                quantity=proposal.quantity,
                status=SignalStatus.PENDING,
                generated_at=datetime.now(UTC),
                target_price=proposal.target_price,
                expires_at=datetime.now(UTC) + self._cooldown,
            )
            await uow.signals.add(signal)

            if strategy.status not in _TRADEABLE_STATUSES:
                signal.status = SignalStatus.REJECTED
                signal.rejection_reason = f"Strategy is {strategy.status.value}, not tradeable"
                await uow.signals.update(signal)
                await uow.commit()
                return signal

            signal.status = SignalStatus.APPROVED
            await uow.signals.update(signal)
            await uow.commit()

        if auto_execute:
            await self._execute(strategy, signal, exchange)
        return signal

    async def _is_duplicate(self, uow: UnitOfWork, strategy_id: uuid.UUID, proposal: SignalProposal) -> bool:
        recent = await uow.signals.list_for_strategy(strategy_id, limit=5)
        cutoff = datetime.now(UTC) - self._cooldown
        return any(
            existing.side == proposal.side
            and existing.generated_at >= cutoff
            and existing.status != SignalStatus.REJECTED
            for existing in recent
        )

    async def _execute(self, strategy: Strategy, signal: Signal, exchange: ExchangeClient) -> None:
        async with self._uow_factory() as uow:
            try:
                await self._trading_service.place_market_order(
                    user_id=strategy.user_id,
                    exchange=exchange,
                    symbol=signal.symbol,
                    side=signal.side,
                    quantity=signal.quantity,
                    strategy_id=strategy.id,
                    signal_id=signal.id,
                )
            except _REJECTABLE_EXCEPTIONS as exc:
                signal.status = SignalStatus.REJECTED
                signal.rejection_reason = exc.message
                await uow.signals.update(signal)
                await uow.commit()
                return

            signal.status = SignalStatus.CONSUMED
            await uow.signals.update(signal)
            await uow.commit()
