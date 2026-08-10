from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_data import DataStatus


class MarketCode(StrEnum):
    TWSE = "TWSE"
    TPEX = "TPEX"


class SecurityType(StrEnum):
    COMMON_STOCK = "COMMON_STOCK"


class SecurityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass(frozen=True)
class Market:
    code: MarketCode
    name: str
    timezone: str = "Asia/Taipei"


@dataclass(frozen=True)
class Industry:
    code: str
    name: str
    classification_source: str


@dataclass(frozen=True)
class SecurityRecord:
    market: MarketCode
    code: str
    name: str
    security_type: SecurityType
    status: SecurityStatus
    listing_date: date | None
    industry: Industry | None
    source_code: str
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source_revision: str | None = None


@dataclass(frozen=True)
class Security:
    id: UUID
    market: MarketCode
    code: str
    name: str
    security_type: SecurityType
    status: SecurityStatus
    is_active: bool
    listing_date: date | None
    primary_industry: str | None
    source_code: str
    as_of: datetime
    received_at: datetime
    data_status: DataStatus


class SecurityRepository(Protocol):
    async def synchronize(
        self, market: MarketCode, records: list[SecurityRecord], run_id: UUID
    ) -> tuple[int, int, int]: ...
    async def search(self, query: str, market: MarketCode | None, limit: int) -> list[Security]: ...
    async def find_by_code(self, code: str, market: MarketCode | None) -> list[Security]: ...
