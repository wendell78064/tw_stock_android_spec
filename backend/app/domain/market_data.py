from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class DataStatus(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    PRELIMINARY = "PRELIMINARY"
    FINAL = "FINAL"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: Decimal | None
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    missing_reason: str | None = None


class MarketDataProvider(Protocol):
    """Provider boundary; adapters must map upstream fields into domain records."""

    async def get_snapshot(self, symbol: str) -> MarketSnapshot: ...

