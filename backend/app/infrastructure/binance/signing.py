"""HMAC-SHA256 request signing for Binance's SIGNED endpoints.

See https://binance-docs.github.io/apidocs/spot/en/#signed-trade-user_data-and-margin-endpoint-security
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode


def build_query_string(params: dict[str, object]) -> str:
    """Binance requires values URL-encoded in the order supplied; a plain
    `dict` preserves insertion order, so no extra bookkeeping is needed."""
    return urlencode({key: value for key, value in params.items() if value is not None})


def sign_query_string(query_string: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha256).hexdigest()
