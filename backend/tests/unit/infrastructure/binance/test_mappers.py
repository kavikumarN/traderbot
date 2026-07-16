from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.exchange.enums import KlineInterval, OrderSide, OrderStatus, OrderType, SymbolStatus
from app.domain.exchange.exceptions import ExchangeError
from app.infrastructure.binance import mappers


def test_parse_decimal_from_binance_string() -> None:
    assert mappers.parse_decimal("62483.13000000") == Decimal("62483.13000000")


def test_parse_decimal_rejects_garbage() -> None:
    with pytest.raises(ExchangeError):
        mappers.parse_decimal("not-a-number")


def test_parse_timestamp_ms() -> None:
    dt = mappers.parse_timestamp_ms(1735689600000)
    assert dt.year == 2025
    assert dt.tzinfo is not None


def test_to_symbol_info_reads_all_three_filters() -> None:
    raw = {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "filters": [
            {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"},
            {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000", "stepSize": "0.00001"},
            {"filterType": "NOTIONAL", "minNotional": "5.00000000"},
        ],
    }
    info = mappers.to_symbol_info(raw)
    assert info.symbol == "BTCUSDT"
    assert info.status == SymbolStatus.TRADING
    assert info.price_filter.tick_size == Decimal("0.01")
    assert info.lot_size_filter.step_size == Decimal("0.00001")
    assert info.notional_filter.min_notional == Decimal("5.00000000")


def test_to_symbol_info_falls_back_to_min_notional_filter_type() -> None:
    raw = {
        "symbol": "BTCUSDT",
        "baseAsset": "BTC",
        "quoteAsset": "USDT",
        "status": "TRADING",
        "filters": [{"filterType": "MIN_NOTIONAL", "minNotional": "10"}],
    }
    info = mappers.to_symbol_info(raw)
    assert info.notional_filter.min_notional == Decimal("10")


def test_to_symbol_info_handles_missing_filters() -> None:
    raw = {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "BREAK", "filters": []}
    info = mappers.to_symbol_info(raw)
    assert info.price_filter is None
    assert info.lot_size_filter is None
    assert info.notional_filter is None
    assert info.status == SymbolStatus.BREAK


def test_to_exchange_info() -> None:
    raw = {
        "serverTime": 1735689600000,
        "symbols": [
            {"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT", "status": "TRADING", "filters": []}
        ],
    }
    info = mappers.to_exchange_info(raw)
    assert len(info.symbols) == 1
    assert info.get_symbol("BTCUSDT") is not None


def test_to_ticker() -> None:
    raw = {
        "symbol": "BTCUSDT",
        "lastPrice": "62483.13",
        "bidPrice": "62483.13",
        "askPrice": "62483.14",
        "highPrice": "63000",
        "lowPrice": "62000",
        "volume": "1000",
        "quoteVolume": "62000000",
        "priceChangePercent": "-1.2",
        "openTime": 1735689600000,
        "closeTime": 1735776000000,
    }
    ticker = mappers.to_ticker(raw)
    assert ticker.symbol == "BTCUSDT"
    assert ticker.last_price == Decimal("62483.13")
    assert ticker.price_change_percent == Decimal("-1.2")


def test_to_order_book() -> None:
    raw = {"lastUpdateId": 42, "bids": [["100", "1"]], "asks": [["101", "2"]]}
    book = mappers.to_order_book("BTCUSDT", raw)
    assert book.last_update_id == 42
    assert book.bids[0].price == Decimal("100")
    assert book.asks[0].quantity == Decimal("2")


def test_to_candle_reads_kline_array_positionally() -> None:
    raw = [1735689600000, "1", "2", "0.5", "1.5", "100", 1735689659999, "150", 42]
    candle = mappers.to_candle("BTCUSDT", KlineInterval.ONE_MINUTE, raw)
    assert candle.open == Decimal("1")
    assert candle.high == Decimal("2")
    assert candle.low == Decimal("0.5")
    assert candle.close == Decimal("1.5")
    assert candle.volume == Decimal("100")
    assert candle.trade_count == 42
    assert candle.is_closed is True


def test_to_trade() -> None:
    raw = {"id": 1, "price": "100", "qty": "2", "quoteQty": "200", "time": 1735689600000, "isBuyerMaker": True}
    trade = mappers.to_trade("BTCUSDT", raw)
    assert trade.trade_id == 1
    assert trade.quote_quantity == Decimal("200")
    assert trade.is_buyer_maker is True


def test_to_asset_balance() -> None:
    balance = mappers.to_asset_balance({"asset": "BTC", "free": "1.5", "locked": "0.5"})
    assert balance.total == Decimal("2.0")


class TestToExchangeOrder:
    def _raw(self, **overrides: object) -> dict:
        raw = {
            "symbol": "BTCUSDT",
            "orderId": 28,
            "clientOrderId": "abc123",
            "price": "0.00000000",
            "origQty": "10.00000000",
            "executedQty": "10.00000000",
            "cummulativeQuoteQty": "500000.00000000",
            "status": "FILLED",
            "timeInForce": "GTC",
            "type": "MARKET",
            "side": "SELL",
            "transactTime": 1735689600000,
        }
        raw.update(overrides)
        return raw

    def test_handles_the_double_m_typo_field(self) -> None:
        order = mappers.to_exchange_order(self._raw())
        assert order.cumulative_quote_quantity == Decimal("500000.00000000")

    def test_handles_open_orders_shape_with_time_and_update_time(self) -> None:
        raw = self._raw()
        del raw["transactTime"]
        raw["time"] = 1735689600000
        raw["updateTime"] = 1735689660000
        order = mappers.to_exchange_order(raw)
        assert order.created_at.timestamp() * 1000 == 1735689600000
        assert order.updated_at.timestamp() * 1000 == 1735689660000

    def test_maps_enums_correctly(self) -> None:
        order = mappers.to_exchange_order(self._raw())
        assert order.side == OrderSide.SELL
        assert order.type == OrderType.MARKET
        assert order.status == OrderStatus.FILLED


def test_to_exchange_order_from_execution_report_uses_single_letter_keys() -> None:
    raw = {
        "e": "executionReport",
        "s": "BTCUSDT",
        "c": "abc123",
        "S": "BUY",
        "o": "LIMIT",
        "f": "GTC",
        "i": 12345,
        "p": "50000",
        "q": "1",
        "z": "0.5",
        "Z": "25000",
        "X": "PARTIALLY_FILLED",
        "O": 1735689600000,
        "T": 1735689601000,
        "E": 1735689601000,
    }
    order = mappers.to_exchange_order_from_execution_report(raw)
    assert order.exchange_order_id == 12345
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.executed_quantity == Decimal("0.5")
    assert order.cumulative_quote_quantity == Decimal("25000")
