# TraderBot — Path to a World-Class, Real-Money Platform

`TODO.md` covers hardening what already exists (bugs, missing tests,
infrastructure gaps). This file is the opposite direction: new modules and
capabilities that separate a hobbyist bot from an institutional-grade
platform. Grouped by theme, roughly ordered by how directly each one affects
whether real capital should be trusted to this system.

Today's shape, for context: single exchange (Binance), spot-only, one quote
asset per position, OHLCV-only market data, single-instance deployment,
plugin-based strategies (EMA/RSI/MACD/Grid/VWAP/Breakout), a risk engine with
per-strategy limits, and paper + live trading modes.

---

## 1. Risk management — the difference between a bot and a fiduciary

This is the highest-leverage category. A backtester with a great Sharpe ratio
means nothing if the risk engine can't protect capital in a real, live,
adversarial market.

- **Portfolio-level VaR/CVaR, computed live, not just in backtests.** Today's
  risk engine limits are per-strategy; a real risk system needs to know the
  *combined* exposure and correlation across every open position before
  approving a new order.
- **Correlation-aware position sizing.** Five strategies all long BTC-
  correlated alts isn't five independent bets — it's one large concentrated
  bet wearing five costumes.
- **Circuit breakers with real teeth**: per-exchange, per-symbol, and
  market-wide (flash-crash detection — e.g. auto-halt new entries if price
  moves N% in under M seconds, a real and recurring crypto market event).
- **Drawdown-based de-risking.** Automatically cut position sizes (not just
  alert) once realized drawdown crosses a threshold, and require manual
  re-arm rather than silently resuming at full size.
- **Reconciliation engine.** Periodically diff the platform's believed
  positions/balances against what the exchange actually reports and alert
  loudly on drift — the single most common cause of real trading losses is
  "the bot thought it had no position and it did."
- **Idempotent order placement** with `client_order_id` dedup on every retry
  path (network timeout ≠ order didn't happen — a real risk if any order
  placement code retries blindly today).

## 2. Multi-exchange and multi-asset-class support

The `ExchangeClient`/`IMarketDataReader` hexagonal ports already make this
architecturally cheap — it's "write another adapter," not "redesign the
system."

- **More spot exchange adapters** (Coinbase, Kraken, Bybit, OKX) — beyond
  redundancy, this enables:
  - **Cross-exchange best-execution routing** (place where price/liquidity
    is best right now).
  - **Cross-exchange arbitrage detection** as a strategy class of its own.
  - **Exchange outage failover** — if Binance has an incident, keep trading
    elsewhere instead of going dark.
- **Perpetual futures / margin support** — funding rate accounting, leverage
  limits, liquidation-price tracking, margin-call handling. Large scope, but
  it's where a lot of real crypto trading volume actually lives.
- **Multi-quote-asset portfolios** (not just USDT) with proper cross-currency
  valuation.

## 3. Execution quality — how professionals actually place orders

Right now every order is a single market or limit order. Real execution
desks never do that with size.

- **TWAP/VWAP execution algorithms** — slice a large order over time to
  reduce market impact.
- **Iceberg orders** — hide true order size from the book.
- **Post-only / maker-only enforcement** to control fee tier and avoid
  paying the taker spread when it's not necessary.
- **Transaction cost analysis (TCA)** — measure realized slippage against
  arrival price per order, not just per backtest; feed it back into strategy
  evaluation. ("Implementation shortfall" is the standard term for this.)
- **Dynamic position sizing from live liquidity/volatility**, not just a
  fixed lot size or flat % of equity — an order that's fine in calm markets
  can move the price badly in thin ones.

## 4. Market data depth — OHLCV isn't enough for real signal generation

The backtest engine's own docstring already flags this limitation honestly:
"candles carry OHLCV, not a real order book."

- **Level 2 order book capture and storage** — enables real market-
  microstructure strategies (order flow imbalance, spoofing detection,
  liquidity-taking cost modeling) and far more realistic backtests than the
  volume-fraction heuristic currently used for partial fills.
- **On-chain data** (exchange inflow/outflow, whale wallet movement, DeFi
  TVL) as a genuinely differentiated crypto-native signal source.
- **Derivatives market data** (funding rates, open interest, put/call ratio)
  as sentiment/positioning indicators, even for a spot-only strategy.
- **Broader sentiment**: the existing news feed is a good start; real
  desks also watch social/on-chain sentiment velocity, not just headlines.

## 5. Compliance, accounting, and audit — required the moment real money moves

- **Tax lot accounting** (FIFO/LIFO/HIFO) and exportable tax reports — this
  is a near-universal real-world need the moment trading is for real capital,
  and it's absent today.
- **Immutable, tamper-evident audit trail** for every order and every risk
  override (append-only log, ideally with cryptographic chaining) — "what did
  the system decide and why" needs to survive a dispute or an incident
  post-mortem.
- **Trade surveillance** (wash trading, spoofing self-checks) if the platform
  ever operates at a scale where exchanges or regulators would care.
- **Best-execution documentation** — if this ever manages third-party money,
  "we can prove we sought the best price" stops being optional.

## 6. Strategy research & development tooling

- **Notebook/research environment integration** — pull historical candles
  and backtest results into pandas for ad hoc research, rather than only
  through the REST API.
- **Shadow/paper A-B testing of a new strategy against the live one**,
  side by side, before committing real capital to it.
- **A documented strategy SDK** if third parties (or future-you in six
  months) should be able to write a new `StrategyPlugin` without reading the
  whole codebase first.
- **A feature store** for engineered indicators/features — versioned and
  cached, so ML-based strategies (see `TODO.md` §8) aren't recomputing the
  same features from scratch per run.

## 7. Portfolio & wealth-management layer

- **Performance attribution** — which strategy, symbol, or time period
  actually drove returns, not just an aggregate equity curve.
- **Benchmark comparison** (vs. BTC buy-and-hold, a custom index) — a
  strategy's absolute return means little without a benchmark.
- **Rebalancing engine** for target-allocation drift correction.
- **DCA (dollar-cost averaging)** as a first-class scheduled feature, not
  just something a custom strategy plugin could technically do.
- **Multi-account/sub-account segregation** if this ever serves more than
  one trader or client from one deployment.

## 8. Operational resilience for a system holding real capital

- **Hot-standby / failover for the strategy engine** — it's single-instance
  and holds state in memory today; a crash mid-session means whatever wasn't
  persisted is gone.
- **Multi-region deployment** with health-based failover.
- **Exchange health monitoring** independent of the platform's own uptime
  (detect "Binance is degraded" vs. "we are degraded" as different alerts).

## 9. Trading-specific security (beyond general hardening in `TODO.md`)

- **Withdrawal whitelist enforcement** at the exchange-API-key level — a
  trading bot's API key should never be able to withdraw funds, full stop.
- **2FA/MFA** on the platform login and a step-up challenge for sensitive
  actions (large manual orders, risk-limit changes, API key rotation).
- **IP allowlisting** for API access and anomaly detection on login
  (new device, new geography).
- **Hardware-backed or vaulted secret storage** for exchange API keys
  instead of `.env` files, once this is more than a single-operator setup.

## 10. Product surface — what makes it feel "world class" to a user

- **Mobile push notifications** (fills, risk alerts, price alerts) — a
  trading platform that only notifies you while you're staring at a browser
  tab isn't one you can trust unattended.
- **Webhooks** for Slack/Discord alerts and inbound triggers (e.g. a
  TradingView alert placing a paper order for validation).
- **A public, documented API** with its own API keys, if this should ever be
  usable programmatically by someone other than the bundled frontend.
- **Customizable dashboards** — the Insights terminal and Dashboard are
  fixed layouts today; power users eventually want to arrange their own.

---

## Suggested sequencing

1. **Risk management (§1)** and **reconciliation** — the two things most
   likely to actually lose real money if skipped.
2. **Execution quality (§3)** and **tax/audit (§5)** — required the moment
   this trades real, non-trivial size.
3. **Multi-exchange (§2)** — cheap architecturally, high payoff (redundancy
   + best execution), do this before futures/margin.
4. Everything else, driven by which of research tooling, portfolio
   management, or product polish actually matters for how this gets used.

*Companion to `TODO.md` (hardening what exists) — read that one first if
choosing where to start, since a feature built on a shaky foundation just
moves the shakiness somewhere new.*
