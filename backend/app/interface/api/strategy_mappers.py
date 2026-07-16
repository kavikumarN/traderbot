"""Strategy engine domain entity -> API response mapping."""

from __future__ import annotations

from app.domain.strategy.entities import Signal, Strategy
from app.interface.api.schemas.strategy import SignalResponse, StrategyResponse


def strategy_to_response(strategy: Strategy) -> StrategyResponse:
    return StrategyResponse(
        id=strategy.id,
        user_id=strategy.user_id,
        name=strategy.name,
        description=strategy.description,
        symbol=strategy.symbol,
        status=strategy.status.value,
        version=strategy.version,
        strategy_type=strategy.config.get("strategy_type", ""),
        parameters=strategy.config.get("parameters", {}),
        created_at=strategy.created_at,
        updated_at=strategy.updated_at,
    )


def signal_to_response(signal: Signal) -> SignalResponse:
    return SignalResponse(
        id=signal.id,
        strategy_id=signal.strategy_id,
        symbol=signal.symbol,
        side=signal.side,
        quantity=str(signal.quantity),
        target_price=str(signal.target_price) if signal.target_price is not None else None,
        status=signal.status.value,
        rejection_reason=signal.rejection_reason,
        generated_at=signal.generated_at,
        expires_at=signal.expires_at,
    )
