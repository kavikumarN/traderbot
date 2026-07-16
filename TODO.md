# TraderBot — Robustness TODO

A prioritized list of what's left to make this platform production-robust,
based on gaps found while building the Binance SDK integration, backtest
analytics, and realistic order simulation. Ordered roughly by
risk/impact — fix bugs before adding features.

---

## 1. Known bugs (fix first — these are real, confirmed, not hypothetical)

- [ ] **Paper trading order-ID collision on restart.** `PaperTradingExchangeAdapter`
  seeds its order-ID sequence from `itertools.count(1)` in memory. Any backend
  restart resets it to 1, which collides with orders already persisted in
  Postgres from before the restart, causing a `UniqueViolationError` on the
  next reconciliation pass for that order (`(exchange_account_id,
  exchange_order_id)` unique constraint). Confirmed live — happened
  immediately after a routine container restart. Fix: seed the sequence from
  `MAX(exchange_order_id)` for the account on startup, or switch to UUIDs.

- [ ] **Async task-cancellation flakiness (`asyncio`/pytest-asyncio, Python 3.13).**
  A cluster of tests fail/hang intermittently, all in the same family — task
  cancellation isn't settled synchronously when the test asserts right after
  calling `.cancel()`:
  - `tests/unit/application/services/test_strategy_engine.py::test_start_strategy_and_stop_strategy_lifecycle`
  - `tests/unit/application/services/test_strategy_engine.py::test_start_strategy_is_a_no_op_if_already_tracked`
  - `tests/unit/application/services/test_strategy_engine.py::test_stop_stops_every_tracked_strategy`
  - `tests/unit/infrastructure/binance/ws/test_binance_user_data_stream.py::test_keepalive_loop_pings_the_listen_key_periodically` (hangs)
  - `tests/unit/infrastructure/binance/ws/test_binance_user_data_stream.py::test_close_cancels_the_keepalive_task`
  - `tests/unit/application/strategies/test_update_strategy_status.py::test_leaving_tradeable_status_stops_engine_when_supplied`
  Confirmed pre-existing (not caused by any of this session's changes — verified
  by reverting dependency versions and re-testing). Needs someone to sit down
  with `StrategyEngine.stop_strategy`/`BinanceUserDataStream.close` and add a
  proper `await task` (with `CancelledError` swallowed) after `.cancel()`.

- [ ] **`bytes`/`str` mismatch in a signing test.**
  `tests/unit/infrastructure/binance/test_http_client.py::test_post_order_places_params_in_the_url_not_a_body`
  compares a `bytes` literal against a `str` — always fails, unrelated to any
  real signing bug (the code path it's testing works fine in production; the
  assertion itself is wrong: `httpx.URL.query` is `bytes`).

## 2. Live trading — the backtest engine outpaced it

- [ ] **`SignalManager._execute` only ever places market orders.** Every
  built-in strategy plugin can now emit `stop_loss_price`/`take_profit_price`/
  `trailing_stop_pct`/`order_type=LIMIT` on a `SignalProposal` (added for
  backtest realism), but live/paper trading silently ignores all of it —
  `TradingService.place_limit_order`/`place_stop_order` already exist and
  work, they're just never called from the signal pipeline. This is the
  highest-value next step if paper/live trading matters more than backtesting
  right now: wire `SignalManager._execute` to pick the right `TradingService`
  method based on the proposal's new fields, and to place real bracket
  (OCO-style) exit orders once a position opens.
- [ ] Decide whether trailing-stop needs to become a real, continuously
  re-priced resting order on the exchange (Binance doesn't support a native
  trailing-stop order type for spot the same way this backtest engine
  simulates it) — likely needs a background loop that watches price and
  replaces the stop order, not a one-shot placement.

## 3. Backtesting — what's still missing from a "professional" engine

- [ ] **Portfolio-level (multi-symbol) backtesting.** Right now one backtest
  = one strategy = one symbol = one equity curve. No cross-symbol capital
  allocation or correlation.
- [ ] **Walk-forward analysis** (train/validate window rolling forward) and
  **out-of-sample validation** — needed to catch overfit parameter sets.
- [ ] **Monte Carlo simulation** (resample the trade sequence to get a
  distribution of outcomes, not just one path).
- [ ] **Parameter grid search / multi-strategy comparison** — run N backtests
  and rank them. Blocked on background job execution (below); running
  hundreds of backtests synchronously inline in an HTTP request isn't viable.
- [ ] **More visualizations**: monthly returns heatmap (deferred — needs
  multi-year data to be worth it), rolling Sharpe ratio, profit-by-hour/day/
  symbol, trade timeline, exposure chart.
- [ ] **Downloadable reports** — trade log CSV export exists; PDF/Excel
  full-report export doesn't.
- [ ] **Saved backtest history / versioned comparison UI** — backtests are
  persisted per-strategy already (`GET /strategies/{id}/backtests`), but
  there's no side-by-side comparison table in the frontend.
- [ ] Funding fees / borrowing costs are N/A today (spot-only platform, no
  perpetuals or margin anywhere in the codebase) — revisit only if futures/
  margin trading ever gets added.

## 4. Infrastructure — the real blocker for everything in section 3

- [ ] **Background job execution.** Backtests run synchronously inline in the
  request (`RunBacktestUseCase`, capped at `MAX_BACKTEST_CANDLES = 20_000`).
  There is zero job-queue/worker infrastructure in this codebase (no Celery,
  no RQ, no `BackgroundTasks` usage for this). Needed before grid search,
  walk-forward, or Monte Carlo can exist — those mean running many backtests,
  not one.
- [ ] **Progress reporting** for long-running jobs once they're async (poll
  endpoint or WebSocket — `WebSocketManager` already exists for market data
  push, could be reused).
- [ ] **Redis-backed rate limiter.** The Binance exchange rate limiter
  (`InMemoryTokenBucketRateLimiter`) is explicitly in-memory-only per its own
  docstring — fine for one backend replica (which is the current deployment
  shape), but would under/over-count across multiple replicas.
- [ ] General-purpose Redis caching layer doesn't exist yet — Redis today is
  used only for JWT token blacklisting.

## 5. Security & production hardening

- [ ] Secrets are `.env`-file based (fine for one deployment, not for a team/
  multi-environment setup) — consider a real secrets manager if this grows
  past a single operator.
- [ ] No Binance API key rotation process documented or automated.
- [ ] No audit log specifically for risk-engine overrides (emergency stop,
  circuit breaker reset) beyond whatever's in the general request log.
- [ ] No load testing or chaos testing has been done — order placement,
  websocket reconnect, and the strategy engine's background tasks have never
  been tested under real concurrent load.
- [ ] No documented Postgres backup/restore or disaster-recovery procedure.

## 6. Observability

- [ ] Confirm `/metrics` (prometheus-fastapi-instrumentator) is actually
  scraped and has dashboards/alerts wired up in the real deployment, not just
  exposed.
- [ ] No alerting on: risk engine emergency stop triggered, strategy engine
  task crash/silent death, Binance WS disconnect exceeding N reconnect
  attempts, paper-trading order collisions (see bug #1 above — this class of
  bug would have been caught immediately by an alert).

## 7. Testing & quality

- [ ] Full backend suite has 7 known-flaky deselects (section 1) — CI should
  either fix them or explicitly quarantine them so a real regression doesn't
  get lost in the noise.
- [ ] No load/soak test for the strategy engine running many concurrent
  strategies for an extended period (memory leaks, task accumulation).
- [ ] Frontend has no automated test suite at all (no Vitest/Playwright/
  Cypress found) — every verification this session was manual browser
  testing. Worth at least smoke-testing the critical paths (login, place
  order, run backtest) in CI.

## 8. AI-assisted optimization (from the original mega-spec — lowest priority)

Only worth starting after section 4 (background jobs) exists, since every
technique here means running many backtests:
- [ ] Bayesian optimization / genetic algorithm / particle swarm / random
  search for parameter tuning.
- [ ] ML-based market regime classification (trending/ranging/high-vol/
  low-vol) — no ML dependencies exist in the project yet (no scikit-learn/
  torch/tensorflow).
- [ ] Reinforcement learning for strategy improvement — significant scope;
  worth confirming this is actually wanted (vs. aspirational) before
  investing here, given the RL literature's track record for live trading
  is mixed at best and the operational risk of an RL-tuned strategy touching
  real money is high.
- [ ] Natural-language "AI report" (strategy score, before/after comparison,
  plain-English explanation of why trades won/lost) — doable without ML,
  as a rules-based summary over the metrics that already exist
  (`domain/backtesting/analytics.py`).

---

*Generated from findings during the Binance SDK / backtest analytics /
realistic order simulation work — see git history around that period for
the code these items reference.*
