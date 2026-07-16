from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.exchange.enums import SymbolStatus
from app.domain.exchange.models.exchange_info import (
    ExchangeInfo,
    LotSizeFilter,
    NotionalFilter,
    PriceFilter,
    SymbolInfo,
)


def make_symbol_info(**overrides: object) -> SymbolInfo:
    defaults: dict[object, object] = dict(
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        status=SymbolStatus.TRADING,
        price_filter=PriceFilter(min_price=Decimal("0.01"), max_price=Decimal("1000000"), tick_size=Decimal("0.01")),
        lot_size_filter=LotSizeFilter(min_qty=Decimal("0.00001"), max_qty=Decimal("9000"), step_size=Decimal("0.00001")),
        notional_filter=NotionalFilter(min_notional=Decimal("5")),
    )
    defaults.update(overrides)
    return SymbolInfo(**defaults)  # type: ignore[arg-type]


class TestSymbolInfo:
    def test_round_price_floors_to_tick_size(self) -> None:
        info = make_symbol_info()
        assert info.round_price(Decimal("123.4567")) == Decimal("123.45")

    def test_round_price_is_a_no_op_without_a_price_filter(self) -> None:
        info = make_symbol_info(price_filter=None)
        assert info.round_price(Decimal("123.4567")) == Decimal("123.4567")

    def test_round_quantity_floors_to_step_size(self) -> None:
        info = make_symbol_info()
        assert info.round_quantity(Decimal("0.123456")) == Decimal("0.12345")

    def test_meets_min_notional(self) -> None:
        info = make_symbol_info()
        assert info.meets_min_notional(Decimal("10"), Decimal("1")) is True
        assert info.meets_min_notional(Decimal("1"), Decimal("1")) is False

    def test_meets_min_notional_without_a_filter_always_passes(self) -> None:
        info = make_symbol_info(notional_filter=None)
        assert info.meets_min_notional(Decimal("0"), Decimal("0")) is True

    def test_is_trading(self) -> None:
        assert make_symbol_info(status=SymbolStatus.TRADING).is_trading is True
        assert make_symbol_info(status=SymbolStatus.BREAK).is_trading is False


class TestExchangeInfo:
    def test_get_symbol_is_case_insensitive(self) -> None:
        info = ExchangeInfo(server_time=datetime.now(UTC), symbols=(make_symbol_info(),))
        assert info.get_symbol("btcusdt") is not None
        assert info.get_symbol("BTCUSDT") is not None

    def test_get_symbol_returns_none_when_unknown(self) -> None:
        info = ExchangeInfo(server_time=datetime.now(UTC), symbols=())
        assert info.get_symbol("ETHUSDT") is None
