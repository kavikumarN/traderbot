"""Position sizing: pure math translating "how much of my account am I
willing to lose on this trade" into a concrete order quantity and a pair of
protective prices.

These are plain functions, not methods on an entity or a service — they
have no dependency on a `UnitOfWork`, an exchange, or any other I/O, so
`RiskEngine` and any use case (or, eventually, a strategy plugin) can call
them directly. All prices/quantities are `Decimal`; nothing here rounds to
an exchange's lot size or tick size — that's `OrderService`/`ExecutionService`
territory once a concrete order is being built.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.exceptions import ValidationError
from app.domain.exchange.enums import OrderSide

DEFAULT_REWARD_RISK_RATIO = Decimal("2")


def calculate_stop_loss_price(*, entry_price: Decimal, side: OrderSide, stop_loss_pct: Decimal) -> Decimal:
    """The price that caps the loss on this position at `stop_loss_pct` of
    the entry price: below entry for a long (BUY), above entry for a short
    (SELL)."""

    if entry_price <= 0:
        raise ValidationError("entry_price must be positive")
    if not (0 < stop_loss_pct < 1):
        raise ValidationError("stop_loss_pct must be between 0 and 1 (exclusive)")

    offset = entry_price * stop_loss_pct
    return entry_price - offset if side == OrderSide.BUY else entry_price + offset


def calculate_take_profit_price(
    *,
    entry_price: Decimal,
    side: OrderSide,
    stop_loss_price: Decimal,
    reward_risk_ratio: Decimal = DEFAULT_REWARD_RISK_RATIO,
) -> Decimal:
    """The price that banks `reward_risk_ratio` times whatever is being
    risked between `entry_price` and `stop_loss_price` — a 2:1 default
    reward:risk ratio, a common baseline for systematic strategies."""

    if entry_price <= 0:
        raise ValidationError("entry_price must be positive")
    if reward_risk_ratio <= 0:
        raise ValidationError("reward_risk_ratio must be positive")

    risk_per_unit = abs(entry_price - stop_loss_price)
    if risk_per_unit == 0:
        raise ValidationError("stop_loss_price must differ from entry_price")

    reward = risk_per_unit * reward_risk_ratio
    return entry_price + reward if side == OrderSide.BUY else entry_price - reward


def calculate_position_size(
    *,
    equity: Decimal,
    risk_per_trade_pct: Decimal,
    entry_price: Decimal,
    stop_loss_price: Decimal,
) -> Decimal:
    """The classic fixed-fractional sizing formula: risk exactly
    `risk_per_trade_pct` of `equity` on this trade, sized so that a fill at
    `stop_loss_price` realizes exactly that loss.

        quantity = (equity * risk_per_trade_pct) / |entry_price - stop_loss_price|

    Returns `0` (not an error) when `equity` is non-positive — an account
    with no equity yet can't size a position, but that's a normal state
    (e.g. before any funds/paper balance exist), not a validation failure.
    """

    if not (0 < risk_per_trade_pct < 1):
        raise ValidationError("risk_per_trade_pct must be between 0 and 1 (exclusive)")
    if entry_price <= 0:
        raise ValidationError("entry_price must be positive")
    if equity <= 0:
        return Decimal(0)

    risk_per_unit = abs(entry_price - stop_loss_price)
    if risk_per_unit == 0:
        raise ValidationError("stop_loss_price must differ from entry_price")

    risk_amount = equity * risk_per_trade_pct
    return risk_amount / risk_per_unit
