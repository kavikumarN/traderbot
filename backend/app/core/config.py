"""Centralized configuration.

Settings are read once from the environment (and an optional .env file) at
process start and exposed as a cached singleton via ``get_settings()``. Every
other layer depends on this module only through that function, never on
``os.environ`` directly, so behaviour stays testable and overridable.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    app_name: str = "traderbot-backend"
    environment: Literal["local", "staging", "production", "test"] = "local"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "json"

    # --- API ---
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=list)

    # --- Database ---
    database_url: PostgresDsn | str
    database_pool_size: int = 10
    database_max_overflow: int = 5
    database_echo: bool = False

    # --- Redis ---
    redis_url: RedisDsn | str

    # --- Security / JWT ---
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- Password policy ---
    password_min_length: int = 10

    # --- Binance ---
    # API key/secret are optional: public market data (tickers, candles,
    # order book) needs no authentication at all. They're only required
    # once account/order endpoints are actually called.
    binance_api_key: str | None = None
    binance_api_secret: SecretStr | None = None
    binance_rest_base_url: str = "https://api.binance.com"
    binance_ws_base_url: str = "wss://stream.binance.com:9443"
    binance_recv_window_ms: int = 5000
    # Binance's default spot limits: 6000 request-weight/min, 100 orders/10s.
    # See https://binance-docs.github.io/apidocs/spot/en/#limits
    binance_request_weight_limit: int = 6000
    binance_request_weight_window_seconds: float = 60.0
    binance_order_limit: int = 100
    binance_order_window_seconds: float = 10.0
    binance_max_retries: int = 3
    binance_retry_base_delay_seconds: float = 0.5

    # --- Market data engine (Phase 5) ---
    market_data_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    # Kline interval values, e.g. "1m" — kept as plain strings here (parsed
    # into `KlineInterval` where consumed) so `.env` doesn't need to know
    # about the domain enum.
    market_data_candle_intervals: list[str] = Field(default_factory=lambda: ["1m"])
    # Order-book snapshots arrive every ~100ms; persisting every one would
    # be 10 writes/sec/symbol for no benefit (only the latest row is ever
    # read). This throttles *persistence* only — broadcasts to WS clients
    # still happen on every message.
    market_data_order_book_persist_interval_seconds: float = 1.0

    # --- Trading engine (Phase 6) ---
    # "paper" runs every order through the in-memory simulator
    # (`PaperTradingExchangeAdapter`) against real market prices — no order
    # ever reaches Binance. "live" places real orders using the Binance
    # credentials above. Defaults to "paper" so a fresh deployment can never
    # place a real order by accident.
    trading_mode: Literal["paper", "live"] = "paper"
    paper_trading_starting_balance_usdt: Decimal = Decimal("100000")
    paper_trading_commission_rate: Decimal = Decimal("0.001")

    @field_validator("cors_origins", "market_data_symbols", "market_data_candle_intervals", mode="before")
    @classmethod
    def _split_comma_separated_list(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings singleton.

    ``lru_cache`` gives us a single parsed instance without a module-level
    global, and tests can bypass it entirely by constructing ``Settings(...)``
    directly or by clearing the cache after monkeypatching the environment.
    """
    return Settings()  # type: ignore[call-arg]
