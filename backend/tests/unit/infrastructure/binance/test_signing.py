from __future__ import annotations

from app.infrastructure.binance.signing import build_query_string, sign_query_string


def test_build_query_string_preserves_insertion_order() -> None:
    assert build_query_string({"b": 1, "a": 2}) == "b=1&a=2"


def test_build_query_string_drops_none_values() -> None:
    assert build_query_string({"a": 1, "b": None, "c": 3}) == "a=1&c=3"


def test_build_query_string_url_encodes_special_characters() -> None:
    assert build_query_string({"symbol": "BTC USDT"}) == "symbol=BTC+USDT"


def test_sign_query_string_is_deterministic() -> None:
    query = "symbol=BTCUSDT&timestamp=123"
    assert sign_query_string(query, "secret") == sign_query_string(query, "secret")


def test_sign_query_string_differs_by_secret() -> None:
    query = "symbol=BTCUSDT&timestamp=123"
    assert sign_query_string(query, "secret-a") != sign_query_string(query, "secret-b")


def test_sign_query_string_differs_by_query() -> None:
    signature = sign_query_string("symbol=BTCUSDT", "secret")
    assert sign_query_string("symbol=ETHUSDT", "secret") != signature


def test_sign_query_string_is_a_64_char_hex_digest() -> None:
    signature = sign_query_string("symbol=BTCUSDT", "secret")
    assert len(signature) == 64
    int(signature, 16)  # raises ValueError if not valid hex
