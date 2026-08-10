from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode


class PriceBasis(StrEnum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"


class CandleInterval(StrEnum):
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1mo"


class ChartRange(StrEnum):
    ONE_DAY = "1D"
    FIVE_DAYS = "5D"
    TEN_DAYS = "10D"
    THIRTY_DAYS = "30D"
    ONE_YEAR = "1Y"
    FIVE_YEARS = "5Y"


@dataclass(frozen=True)
class SecurityKey:
    market: MarketCode
    code: str


@dataclass(frozen=True)
class DailyPriceRecord:
    security: SecurityKey
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    adjusted_open: Decimal | None
    adjusted_high: Decimal | None
    adjusted_low: Decimal | None
    adjusted_close: Decimal | None
    volume_shares: int | None
    turnover_amount: Decimal | None
    source_code: str
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source_revision: str | None = None
    missing_reason: str | None = None

    @property
    def has_trade(self) -> bool:
        return all(value is not None for value in (self.open, self.high, self.low, self.close))


@dataclass(frozen=True)
class Candle:
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int | None
    turnover_amount: Decimal | None


@dataclass(frozen=True)
class TechnicalSnapshot:
    security: SecurityKey
    trade_date: date
    price_basis: PriceBasis
    values: dict[str, Decimal | None]
    algorithm_version: str
    as_of: datetime
    received_at: datetime
    data_status: DataStatus


class PriceAdjustmentProvider(Protocol):
    async def adjusted_prices(
        self, security: SecurityKey, start_date: date, end_date: date
    ) -> list[DailyPriceRecord]: ...


class PriceRepository(Protocol):
    async def synchronize(
        self, records: list[DailyPriceRecord], run_id: UUID
    ) -> tuple[int, int]: ...

    async def list_prices(
        self, security: SecurityKey, start_date: date | None, end_date: date | None
    ) -> list[DailyPriceRecord]: ...

    async def replace_technicals(
        self, security: SecurityKey, basis: PriceBasis, snapshots: list[TechnicalSnapshot]
    ) -> None: ...

    async def list_technicals(
        self,
        security: SecurityKey,
        basis: PriceBasis,
        start_date: date | None,
        end_date: date | None,
    ) -> list[TechnicalSnapshot]: ...
