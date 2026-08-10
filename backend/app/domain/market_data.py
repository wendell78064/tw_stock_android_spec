from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.domain.pricing import DailyPriceRecord, SecurityKey
    from app.domain.security import SecurityRecord


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

    async def list_securities(self) -> list["SecurityRecord"]: ...

    async def get_daily_prices(
        self,
        trade_date: date | None = None,
        security: "SecurityKey | None" = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list["DailyPriceRecord"]: ...
