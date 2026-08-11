from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_spot import InstitutionType, SourceMetadata
from app.domain.market_spot import LicenseStatus, ProviderPolicy, SourceCapability, SourceType


class VixSourceCapability(StrEnum):
    OPENAPI = "OPENAPI"
    OFFICIAL_DOWNLOAD = "OFFICIAL_DOWNLOAD"
    LICENSED_VENDOR = "LICENSED_VENDOR"
    UNAVAILABLE = "UNAVAILABLE"


TAIWAN_VIX_POLICY = ProviderPolicy(
    SourceType.OFFICIAL_DOWNLOAD,
    SourceCapability.LICENSE_REQUIRED,
    LicenseStatus.PUBLIC_DOWNLOAD_UNVERIFIED_REUSE,
    None,
    None,
    None,
)


class SessionType(StrEnum):
    REGULAR = "REGULAR"
    AFTER_HOURS = "AFTER_HOURS"
    COMBINED = "COMBINED"


class ContractStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class RollMethod(StrEnum):
    VOLUME = "VOLUME"
    OPEN_INTEREST = "OPEN_INTEREST"
    EXPIRY = "EXPIRY"


class PositionSide(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class OptionType(StrEnum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass(frozen=True)
class FuturesProduct:
    code: str
    name: str
    contract_multiplier: Decimal
    currency: str
    session_type: SessionType
    is_active: bool = True


@dataclass(frozen=True)
class FuturesContract:
    product_code: str
    contract_code: str
    contract_month: str
    expiry_date: date
    last_trade_date: date
    status: ContractStatus
    is_active: bool


@dataclass(frozen=True)
class FuturesDailyPrice:
    product_code: str
    contract_code: str
    contract_month: str
    trade_date: date
    session_type: SessionType
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    settlement_price: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    volume: int | None
    open_interest: int | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class InstitutionFuturesPosition:
    product_code: str
    trade_date: date
    institution_type: InstitutionType
    long_volume: int | None
    short_volume: int | None
    net_volume: int | None
    long_amount: Decimal | None
    short_amount: Decimal | None
    net_amount: Decimal | None
    long_oi: int | None
    short_oi: int | None
    net_oi: int | None
    long_oi_amount: Decimal | None
    short_oi_amount: Decimal | None
    net_oi_amount: Decimal | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class TraderConcentration:
    product_code: str
    trade_date: date
    contract_scope: str
    side: PositionSide
    top_n: int
    open_interest: int | None
    market_open_interest: int | None
    concentration_ratio: Decimal | None
    specific_institution_oi: int | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class OptionPutCallRatio:
    product_code: str
    trade_date: date
    put_volume: int | None
    call_volume: int | None
    volume_put_call_ratio: Decimal | None
    put_open_interest: int | None
    call_open_interest: int | None
    oi_put_call_ratio: Decimal | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class OptionStrikeOpenInterest:
    product_code: str
    expiry: str
    trade_date: date
    option_type: OptionType
    strike: Decimal
    open_interest: int | None
    volume: int | None
    settlement_price: Decimal | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class VolatilityIndex:
    code: str
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    metadata: SourceMetadata


@dataclass(frozen=True)
class ContinuousFuturesPoint:
    product_code: str
    trade_date: date
    roll_method: RollMethod
    source_contract: str
    roll_date: date | None
    adjustment_method: str
    algorithm_version: str
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None
    open_interest: int | None
    metadata: SourceMetadata


class DerivativesDataProvider(Protocol):
    source_code: str

    async def get_futures_products(self) -> list[FuturesProduct]: ...
    async def get_futures_contracts(self, trade_date: date) -> list[FuturesContract]: ...
    async def get_futures_daily(self, trade_date: date) -> list[FuturesDailyPrice]: ...
    async def get_futures_institutional_positions(
        self, trade_date: date
    ) -> list[InstitutionFuturesPosition]: ...
    async def get_trader_concentration(self, trade_date: date) -> list[TraderConcentration]: ...
    async def get_put_call_ratio(self, trade_date: date) -> list[OptionPutCallRatio]: ...
    async def get_option_open_interest_by_strike(
        self, trade_date: date
    ) -> list[OptionStrikeOpenInterest]: ...
    async def get_volatility_index(self, trade_date: date) -> list[VolatilityIndex]: ...


class DerivativesRepository(Protocol):
    async def synchronize(
        self, dataset: str, records: list[object], run_id: UUID
    ) -> tuple[int, int]: ...
    async def products(self, product_code: str | None = None) -> list[FuturesProduct]: ...
    async def contracts(self, product_code: str) -> list[FuturesContract]: ...
    async def daily(
        self, product_code: str, contract_code: str | None, limit: int
    ) -> list[FuturesDailyPrice]: ...
    async def positions(
        self, product_code: str, limit: int
    ) -> list[InstitutionFuturesPosition]: ...
    async def concentrations(self, product_code: str, limit: int) -> list[TraderConcentration]: ...
    async def put_call(self, product_code: str, limit: int) -> list[OptionPutCallRatio]: ...
    async def strike_oi(
        self, product_code: str, expiry: str | None, trade_date: date | None
    ) -> list[OptionStrikeOpenInterest]: ...
    async def volatility(self, code: str, limit: int) -> list[VolatilityIndex]: ...
