"""The composed Exchange Adapter Pattern port.

Most call sites should depend on ``IMarketDataReader`` / ``IAccountReader``
/ ``IOrderPlacer`` individually (Interface Segregation) — this combined
port exists for the rare caller (e.g. a future execution-service) that
genuinely needs full exchange access through one object, and for the
adapter class itself to declare what it implements.
"""

from __future__ import annotations

from abc import ABC

from app.domain.exchange.ports.account_reader import IAccountReader
from app.domain.exchange.ports.market_data_reader import IMarketDataReader
from app.domain.exchange.ports.order_placer import IOrderPlacer


class ExchangeClient(IMarketDataReader, IAccountReader, IOrderPlacer, ABC):
    """Implemented per-exchange (e.g. ``BinanceExchangeAdapter``). Adding a
    second exchange later means writing one more class here — nothing that
    depends on this port changes."""
