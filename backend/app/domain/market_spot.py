from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode


class InstitutionType(StrEnum):
    FOREIGN = "FOREIGN"
    INVESTMENT_TRUST = "INVESTMENT_TRUST"
    DEALER = "DEALER"
    TOTAL = "TOTAL"


class DealerSubtype(StrEnum):
    PROPRIETARY = "PROPRIETARY"
    HEDGE = "HEDGE"
    TOTAL = "TOTAL"


@dataclass(frozen=True)
class SourceMetadata:
    source_code: str
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source_revision: str | None = None
    ingestion_run_id: UUID | None = None


@dataclass(frozen=True)
class MarketIndexRecord:
    code: str
    name: str
    market: MarketCode
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    turnover_amount: Decimal | None
    volume: int | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class MarketBreadthRecord:
    market: MarketCode
    trade_date: date
    advancers: int | None
    decliners: int | None
    unchanged: int | None
    limit_up: int | None
    limit_down: int | None
    total_traded: int | None
    turnover_amount: Decimal | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class InstitutionalRecord:
    market: MarketCode
    trade_date: date
    institution_type: InstitutionType
    dealer_subtype: DealerSubtype | None
    buy: Decimal | int | None
    sell: Decimal | int | None
    net: Decimal | int | None
    metadata: SourceMetadata
    security: SecurityKey | None = None
    is_amount: bool = True


@dataclass(frozen=True)
class MarginRecord:
    market: MarketCode
    trade_date: date
    margin_buy: int | None
    margin_sell: int | None
    margin_cash_repayment: int | None
    margin_balance: int | None
    margin_balance_change: int | None
    short_sell: int | None
    short_cover: int | None
    short_stock_repayment: int | None
    short_balance: int | None
    short_balance_change: int | None
    short_margin_ratio: Decimal | None
    metadata: SourceMetadata
    security: SecurityKey | None = None
    margin_utilization: Decimal | None = None
    short_utilization: Decimal | None = None


@dataclass(frozen=True)
class LendingRecord:
    market: MarketCode
    trade_date: date
    lending_sell: int | None
    lending_return: int | None
    lending_balance: int | None
    lending_balance_change: int | None
    metadata: SourceMetadata
    security: SecurityKey | None = None


class MarketSpotProvider(Protocol):
    source_code: str

    async def get_market_indexes(self, trade_date: date) -> list[MarketIndexRecord]: ...
    async def get_market_breadth(self, trade_date: date) -> list[MarketBreadthRecord]: ...
    async def get_market_institutional_spot(
        self, trade_date: date
    ) -> list[InstitutionalRecord]: ...
    async def get_security_institutional_spot(
        self, trade_date: date
    ) -> list[InstitutionalRecord]: ...
    async def get_market_margin_trading(self, trade_date: date) -> list[MarginRecord]: ...
    async def get_security_margin_trading(self, trade_date: date) -> list[MarginRecord]: ...
    async def get_market_securities_lending(self, trade_date: date) -> list[LendingRecord]: ...
    async def get_security_securities_lending(self, trade_date: date) -> list[LendingRecord]: ...


class MarketSpotRepository(Protocol):
    async def synchronize(
        self, dataset: str, records: list[object], run_id: UUID
    ) -> tuple[int, int]: ...
    async def indexes(
        self, code: str | None, start: date | None, end: date | None, limit: int | None = None
    ) -> list[MarketIndexRecord]: ...
    async def breadth(
        self, market: MarketCode | None, start: date | None, end: date | None
    ) -> list[MarketBreadthRecord]: ...
    async def institutional(
        self,
        market: MarketCode,
        security: SecurityKey | None,
        start: date | None,
        end: date | None,
        institution: InstitutionType | None = None,
    ) -> list[InstitutionalRecord]: ...
    async def margins(
        self, market: MarketCode, security: SecurityKey | None, start: date | None, end: date | None
    ) -> list[MarginRecord]: ...
    async def lending(
        self, market: MarketCode, security: SecurityKey | None, start: date | None, end: date | None
    ) -> list[LendingRecord]: ...
