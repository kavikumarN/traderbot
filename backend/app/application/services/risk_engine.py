"""Risk Engine (Phase 8): the gate every order must pass before it ever
reaches an exchange.

Deliberately stateless like `OrderService`/`ExecutionService` — no
`uow_factory`, no owned transaction. Every method takes an already-open
`UnitOfWork` so its caller (`TradingService`) controls the commit boundary;
a rejected order and the risk state that rejected it land in the same
transaction as the order itself.

Two layers of protection:

1. Account-wide hard stops, checked first and raised as exceptions (same
   idiom `ExecutionService` uses for exchange rejections): an active
   **emergency stop** (a human halted this account) or an open **circuit
   breaker** (this engine itself halted it, automatically, after a prior
   breach) blocks every order outright, independent of which rules are
   configured.
2. Per-order rule evaluation: every active `RiskRule` for the account/
   strategy is checked against the proposed order (symbol whitelist,
   position notional, portfolio exposure/leverage, order rate, daily loss,
   drawdown, risk-per-trade) plus a composite 0-100 risk score. Any
   violation raises `RiskLimitExceededError` (with every reason that
   fired) but leaves the account otherwise tradeable — unlike the hard
   stops above, this doesn't trip the circuit breaker by itself.

`record_fill` closes the loop: once a fill realizes pnl, it updates the
same daily-loss/drawdown/consecutive-loss counters `evaluate` reads, and
trips the circuit breaker itself if a threshold is breached — so a bad run
of trades halts the account before `evaluate` is even asked again, not just
retroactively next time it's called.

Position sizing (`suggest_position_size`) is offered as a calculator, not a
gate: this platform's `SignalProposal`/`Order` have no bracket-order
concept (no OCO, no attached take-profit), so recommended stop-loss/
take-profit prices are informational — a caller (a strategy, or a human via
the API) that wants a protective stop must place it itself via
`TradingService.place_stop_order`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.exceptions import ValidationError
from app.domain.exchange.enums import OrderSide
from app.domain.risk.assessment import RiskAssessment
from app.domain.risk.entities import RiskRule, RiskState
from app.domain.risk.enums import CircuitBreakerState, RiskRuleType
from app.domain.risk.exceptions import (
    CircuitBreakerTrippedError,
    EmergencyStopActiveError,
    RiskLimitExceededError,
)
from app.domain.risk.position_sizing import (
    calculate_position_size,
    calculate_stop_loss_price,
    calculate_take_profit_price,
)
from app.domain.trading.entities import ExchangeAccount, Order, Position

DEFAULT_MAX_OPEN_TRADES = 10
DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT = Decimal("0.5")
DEFAULT_MAX_DAILY_LOSS_PCT = Decimal("0.05")
DEFAULT_MAX_DRAWDOWN_PCT = Decimal("0.2")
DEFAULT_RISK_PER_TRADE_PCT = Decimal("0.01")
DEFAULT_STOP_LOSS_PCT = Decimal("0.02")
DEFAULT_REWARD_RISK_RATIO = Decimal("2")
DEFAULT_CONSECUTIVE_LOSS_LIMIT = 5
DEFAULT_CIRCUIT_BREAKER_COOLDOWN = timedelta(hours=1)
DEFAULT_MAX_RISK_SCORE = Decimal("90")
DEFAULT_ORDER_RATE_WINDOW_SECONDS = 60
_ORDER_HISTORY_LOOKBACK = 200


class RiskEngine:
    def __init__(
        self,
        *,
        default_max_open_trades: int = DEFAULT_MAX_OPEN_TRADES,
        default_max_portfolio_exposure_pct: Decimal = DEFAULT_MAX_PORTFOLIO_EXPOSURE_PCT,
        default_max_daily_loss_pct: Decimal = DEFAULT_MAX_DAILY_LOSS_PCT,
        default_max_drawdown_pct: Decimal = DEFAULT_MAX_DRAWDOWN_PCT,
        default_risk_per_trade_pct: Decimal = DEFAULT_RISK_PER_TRADE_PCT,
        default_stop_loss_pct: Decimal = DEFAULT_STOP_LOSS_PCT,
        default_reward_risk_ratio: Decimal = DEFAULT_REWARD_RISK_RATIO,
        consecutive_loss_limit: int = DEFAULT_CONSECUTIVE_LOSS_LIMIT,
        circuit_breaker_cooldown: timedelta = DEFAULT_CIRCUIT_BREAKER_COOLDOWN,
        max_risk_score: Decimal = DEFAULT_MAX_RISK_SCORE,
        quote_asset: str = "USDT",
    ) -> None:
        self._default_max_open_trades = default_max_open_trades
        self._default_max_portfolio_exposure_pct = default_max_portfolio_exposure_pct
        self._default_max_daily_loss_pct = default_max_daily_loss_pct
        self._default_max_drawdown_pct = default_max_drawdown_pct
        self._default_risk_per_trade_pct = default_risk_per_trade_pct
        self._default_stop_loss_pct = default_stop_loss_pct
        self._default_reward_risk_ratio = default_reward_risk_ratio
        self._consecutive_loss_limit = consecutive_loss_limit
        self._circuit_breaker_cooldown = circuit_breaker_cooldown
        self._max_risk_score = max_risk_score
        self._quote_asset = quote_asset.upper()

    # --- the gate ---------------------------------------------------------------------------

    async def evaluate(
        self,
        uow: UnitOfWork,
        *,
        order: Order,
        account: ExchangeAccount,
        strategy_id: uuid.UUID | None = None,
    ) -> RiskAssessment:
        now = datetime.now(UTC)
        state = await self._load_state(uow, account.user_id, now)
        state.roll_daily_window(now.date())
        state.auto_resume_if_due(now)

        if state.emergency_stop:
            state.updated_at = now
            await uow.risk_state.upsert(state)
            raise EmergencyStopActiveError(state.emergency_stop_reason or "manually halted")

        if state.circuit_breaker == CircuitBreakerState.OPEN:
            state.updated_at = now
            await uow.risk_state.upsert(state)
            raise CircuitBreakerTrippedError(
                state.circuit_breaker_reason or "risk limit breached", state.circuit_breaker_resume_at
            )

        rules = await self._active_rules(uow, account.user_id, strategy_id)
        equity = await self.compute_equity(uow, account)
        open_positions = await uow.positions.list_open_for_account(account.id)
        recent_orders = await uow.orders.list_for_account(account.id, limit=_ORDER_HISTORY_LOOKBACK)
        reference_price = _reference_price(order, open_positions)

        reasons = [
            violation
            for rule in rules
            if (
                violation := self._check_rule(
                    rule,
                    order=order,
                    state=state,
                    equity=equity,
                    open_positions=open_positions,
                    recent_orders=recent_orders,
                    reference_price=reference_price,
                )
            )
            is not None
        ]

        risk_score = self._compute_risk_score(
            rules=rules,
            equity=equity,
            open_positions=open_positions,
            state=state,
            reference_price=reference_price,
            order=order,
        )
        if not reasons and risk_score >= self._max_risk_score:
            reasons.append(f"Composite risk score {risk_score} is at/above the {self._max_risk_score} limit")

        recommended_stop_loss: Decimal | None = None
        recommended_take_profit: Decimal | None = None
        if reference_price is not None:
            try:
                recommended_stop_loss = calculate_stop_loss_price(
                    entry_price=reference_price, side=order.side, stop_loss_pct=self._default_stop_loss_pct
                )
                recommended_take_profit = calculate_take_profit_price(
                    entry_price=reference_price,
                    side=order.side,
                    stop_loss_price=recommended_stop_loss,
                    reward_risk_ratio=self._default_reward_risk_ratio,
                )
            except ValidationError:
                pass

        state.updated_at = now
        await uow.risk_state.upsert(state)

        if reasons:
            raise RiskLimitExceededError(reasons)

        return RiskAssessment(
            approved=True,
            risk_score=risk_score,
            reasons=reasons,
            recommended_stop_loss=recommended_stop_loss,
            recommended_take_profit=recommended_take_profit,
        )

    async def record_fill(
        self, uow: UnitOfWork, *, account: ExchangeAccount, realized_pnl_delta: Decimal
    ) -> RiskState:
        """Folds a fill's newly-realized pnl into the account's running
        daily-loss/drawdown/consecutive-loss counters and, if any of those
        now breach an active rule, trips the circuit breaker immediately —
        called by `TradingService` right after it applies a fill to a
        `Position`, so a bad trade can halt the account before the next
        order is even proposed."""

        now = datetime.now(UTC)
        state = await self._load_state(uow, account.user_id, now)
        state.roll_daily_window(now.date())

        equity = await self.compute_equity(uow, account)
        state.update_equity_peak(equity)
        state.record_trade_result(realized_pnl_delta)

        if state.circuit_breaker == CircuitBreakerState.CLOSED:
            rules = await self._active_rules(uow, account.user_id, None)
            trip_reason = self._check_auto_trip(rules=rules, state=state, equity=equity)
            if trip_reason is not None:
                state.trip_circuit_breaker(
                    reason=trip_reason, now=now, resume_at=now + self._circuit_breaker_cooldown
                )

        state.updated_at = now
        await uow.risk_state.upsert(state)
        return state

    # --- account equity -----------------------------------------------------------------------

    async def compute_equity(self, uow: UnitOfWork, account: ExchangeAccount) -> Decimal:
        """Cash (this account's quote-asset wallet balance) plus the
        avg-cost notional of every open position — the same weighted-
        average-cost accounting `TradingService` already uses for pnl, not
        a live mark-to-market (this engine has no exchange/price-feed
        dependency by design)."""

        wallets = await uow.wallets.list_for_account(account.id)
        cash = sum((w.total for w in wallets if w.asset.upper() == self._quote_asset), Decimal(0))
        positions = await uow.positions.list_open_for_account(account.id)
        positions_notional = sum((abs(p.quantity) * p.avg_entry_price for p in positions), Decimal(0))
        return cash + positions_notional

    # --- manual controls (used by the risk API's use cases) ------------------------------------

    async def get_state(self, uow: UnitOfWork, *, user_id: uuid.UUID) -> RiskState:
        now = datetime.now(UTC)
        state = await self._load_state(uow, user_id, now)
        state.roll_daily_window(now.date())
        state.auto_resume_if_due(now)
        state.updated_at = now
        await uow.risk_state.upsert(state)
        return state

    async def set_emergency_stop(
        self, uow: UnitOfWork, *, user_id: uuid.UUID, active: bool, reason: str | None
    ) -> RiskState:
        now = datetime.now(UTC)
        state = await self._load_state(uow, user_id, now)
        if active:
            state.activate_emergency_stop(reason=reason or "Manually triggered", now=now)
        else:
            state.deactivate_emergency_stop()
        state.updated_at = now
        await uow.risk_state.upsert(state)
        return state

    async def reset_circuit_breaker(self, uow: UnitOfWork, *, user_id: uuid.UUID) -> RiskState:
        now = datetime.now(UTC)
        state = await self._load_state(uow, user_id, now)
        state.reset_circuit_breaker()
        state.updated_at = now
        await uow.risk_state.upsert(state)
        return state

    async def suggest_position_size(
        self,
        uow: UnitOfWork,
        *,
        account: ExchangeAccount | None,
        side: OrderSide,
        entry_price: Decimal,
        stop_loss_price: Decimal | None = None,
        stop_loss_pct: Decimal | None = None,
        risk_per_trade_pct: Decimal | None = None,
        reward_risk_ratio: Decimal | None = None,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Returns `(quantity, stop_loss_price, take_profit_price)` sized so
        a fill at the stop loses exactly `risk_per_trade_pct` of the
        account's current equity. `account=None` (no exchange account
        provisioned yet) is treated as zero equity, not an error —
        `calculate_position_size` itself returns a `0` quantity rather than
        raising in that case."""

        equity = await self.compute_equity(uow, account) if account is not None else Decimal(0)
        risk_pct = risk_per_trade_pct if risk_per_trade_pct is not None else self._default_risk_per_trade_pct

        if stop_loss_price is None:
            pct = stop_loss_pct if stop_loss_pct is not None else self._default_stop_loss_pct
            stop_loss_price = calculate_stop_loss_price(entry_price=entry_price, side=side, stop_loss_pct=pct)

        take_profit_price = calculate_take_profit_price(
            entry_price=entry_price,
            side=side,
            stop_loss_price=stop_loss_price,
            reward_risk_ratio=reward_risk_ratio if reward_risk_ratio is not None else self._default_reward_risk_ratio,
        )
        quantity = calculate_position_size(
            equity=equity, risk_per_trade_pct=risk_pct, entry_price=entry_price, stop_loss_price=stop_loss_price
        )
        return quantity, stop_loss_price, take_profit_price

    # --- internals -----------------------------------------------------------------------------

    async def _load_state(self, uow: UnitOfWork, user_id: uuid.UUID, now: datetime) -> RiskState:
        state = await uow.risk_state.get_for_user(user_id)
        if state is None:
            state = RiskState(
                id=uuid.uuid4(), user_id=user_id, circuit_breaker=CircuitBreakerState.CLOSED, updated_at=now
            )
        return state

    async def _active_rules(
        self, uow: UnitOfWork, user_id: uuid.UUID, strategy_id: uuid.UUID | None
    ) -> list[RiskRule]:
        if strategy_id is not None:
            return await uow.risk_rules.list_active_for_strategy(strategy_id)
        return [rule for rule in await uow.risk_rules.list_for_user(user_id) if rule.is_active and rule.is_account_wide]

    def _check_rule(
        self,
        rule: RiskRule,
        *,
        order: Order,
        state: RiskState,
        equity: Decimal,
        open_positions: list[Position],
        recent_orders: list[Order],
        reference_price: Decimal | None,
    ) -> str | None:
        if rule.rule_type == RiskRuleType.SYMBOL_WHITELIST:
            allowed = {symbol.upper() for symbol in rule.config.get("symbols", [])}
            if order.symbol.upper() not in allowed:
                return f"Symbol {order.symbol} is not in the allowed symbol list"
            return None

        if rule.rule_type == RiskRuleType.MAX_OPEN_TRADES:
            if len(open_positions) >= rule.threshold:
                return f"Maximum open trades ({int(rule.threshold)}) already reached"
            return None

        if rule.rule_type == RiskRuleType.MAX_ORDER_RATE:
            window_seconds = int(rule.config.get("window_seconds", DEFAULT_ORDER_RATE_WINDOW_SECONDS))
            cutoff = datetime.now(UTC) - timedelta(seconds=window_seconds)
            recent_count = sum(1 for o in recent_orders if o.created_at >= cutoff)
            if recent_count >= rule.threshold:
                return f"Order rate limit ({int(rule.threshold)} per {window_seconds}s) exceeded"
            return None

        if rule.rule_type == RiskRuleType.MAX_POSITION_NOTIONAL:
            if reference_price is None:
                return None
            order_notional = reference_price * order.quantity
            if order_notional > rule.threshold:
                return f"Order notional {order_notional} exceeds max position notional {rule.threshold}"
            return None

        if rule.rule_type in (RiskRuleType.MAX_PORTFOLIO_EXPOSURE, RiskRuleType.MAX_LEVERAGE):
            if reference_price is None or equity <= 0:
                return None
            order_notional = reference_price * order.quantity
            positions_notional = sum((abs(p.quantity) * p.avg_entry_price for p in open_positions), Decimal(0))
            exposure_ratio = (positions_notional + order_notional) / equity
            if exposure_ratio > rule.threshold:
                label = "portfolio exposure" if rule.rule_type == RiskRuleType.MAX_PORTFOLIO_EXPOSURE else "leverage"
                return f"Resulting {label} ratio {exposure_ratio:.4f} exceeds limit {rule.threshold}"
            return None

        if rule.rule_type == RiskRuleType.MAX_DAILY_LOSS:
            if state.daily_loss >= rule.threshold:
                return f"Daily loss {state.daily_loss} is already at/above the limit {rule.threshold}"
            return None

        if rule.rule_type == RiskRuleType.MAX_DRAWDOWN:
            if equity <= 0:
                return None
            drawdown = state.drawdown_pct(equity)
            if drawdown >= rule.threshold:
                return f"Drawdown {drawdown:.4f} is at/above the limit {rule.threshold}"
            return None

        if rule.rule_type == RiskRuleType.RISK_PER_TRADE:
            if reference_price is None or order.stop_price is None or equity <= 0:
                return None
            risk_amount = abs(reference_price - order.stop_price) * order.quantity
            risk_pct = risk_amount / equity
            if risk_pct > rule.threshold:
                return f"Trade risks {risk_pct:.4f} of equity, exceeding the {rule.threshold} risk-per-trade limit"
            return None

        return None

    def _check_auto_trip(self, *, rules: list[RiskRule], state: RiskState, equity: Decimal) -> str | None:
        max_daily_loss = _threshold_for(rules, RiskRuleType.MAX_DAILY_LOSS)
        if max_daily_loss is not None and state.daily_loss >= max_daily_loss:
            return f"Daily loss {state.daily_loss} reached the {max_daily_loss} limit"

        max_drawdown = _threshold_for(rules, RiskRuleType.MAX_DRAWDOWN)
        if max_drawdown is not None and equity > 0:
            drawdown = state.drawdown_pct(equity)
            if drawdown >= max_drawdown:
                return f"Drawdown {drawdown:.4f} reached the {max_drawdown} limit"

        if state.consecutive_losses >= self._consecutive_loss_limit:
            return (
                f"{state.consecutive_losses} consecutive losing trades reached the limit of "
                f"{self._consecutive_loss_limit}"
            )

        return None

    def _compute_risk_score(
        self,
        *,
        rules: list[RiskRule],
        equity: Decimal,
        open_positions: list[Position],
        state: RiskState,
        reference_price: Decimal | None,
        order: Order,
    ) -> Decimal:
        """A heuristic 0-100 composite: how "hot" the account is running
        relative to its own configured (or, absent that, this engine's
        default) limits. Not itself a hard rule unless it crosses
        `max_risk_score` with nothing else tripped — mainly meant as a
        single number a dashboard (or an operator) can watch trend upward
        before any one rule actually breaches."""

        exposure_ratio = Decimal(0)
        if equity > 0:
            positions_notional = sum((abs(p.quantity) * p.avg_entry_price for p in open_positions), Decimal(0))
            order_notional = reference_price * order.quantity if reference_price is not None else Decimal(0)
            exposure_ratio = (positions_notional + order_notional) / equity

        max_exposure = (
            _threshold_for(rules, RiskRuleType.MAX_PORTFOLIO_EXPOSURE) or self._default_max_portfolio_exposure_pct
        )
        exposure_component = (
            min(Decimal(40), (exposure_ratio / max_exposure) * Decimal(40)) if max_exposure > 0 else Decimal(0)
        )

        max_open_trades = _threshold_for(rules, RiskRuleType.MAX_OPEN_TRADES) or Decimal(self._default_max_open_trades)
        open_trades_component = (
            min(Decimal(25), (Decimal(len(open_positions)) / max_open_trades) * Decimal(25))
            if max_open_trades > 0
            else Decimal(0)
        )

        max_daily_loss = _threshold_for(rules, RiskRuleType.MAX_DAILY_LOSS)
        if max_daily_loss is None and equity > 0:
            max_daily_loss = equity * self._default_max_daily_loss_pct
        daily_loss_component = (
            min(Decimal(20), (state.daily_loss / max_daily_loss) * Decimal(20))
            if max_daily_loss and max_daily_loss > 0
            else Decimal(0)
        )

        consecutive_loss_component = min(Decimal(15), Decimal(state.consecutive_losses) * Decimal(3))

        score = exposure_component + open_trades_component + daily_loss_component + consecutive_loss_component
        return min(Decimal(100), score).quantize(Decimal("0.01"))


def _reference_price(order: Order, open_positions: list[Position]) -> Decimal | None:
    """The best price this engine can attribute to `order` without an
    exchange/price-feed dependency: the order's own limit/stop price if it
    carries one, else the avg-cost basis of an existing position in the
    same symbol, else `None` (a fresh MARKET order with no existing
    position gives this engine nothing to price notional/exposure checks
    against — those checks fail open rather than block on missing data)."""

    if order.price is not None:
        return order.price
    if order.stop_price is not None:
        return order.stop_price
    for position in open_positions:
        if position.symbol == order.symbol and not position.is_flat:
            return position.avg_entry_price
    return None


def _threshold_for(rules: list[RiskRule], rule_type: RiskRuleType) -> Decimal | None:
    for rule in rules:
        if rule.rule_type == rule_type:
            return rule.threshold
    return None
