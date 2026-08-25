from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel


class LicenseStatus(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    UNVERIFIED = "UNVERIFIED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    UNCONFIGURED = "UNCONFIGURED"


class DataStatus(StrEnum):
    LIVE = "LIVE"
    STALE = "STALE"
    DELAYED = "DELAYED"
    UNAVAILABLE = "UNAVAILABLE"


class TradingSession(StrEnum):
    REGULAR = "REGULAR"
    AFTER_HOURS = "AFTER_HOURS"
    UNKNOWN = "UNKNOWN"


class RealtimeEventKind(StrEnum):
    SNAPSHOT = "SNAPSHOT"
    UPDATE = "UPDATE"


class RealtimeQuoteType(StrEnum):
    TICK = "tick"
    BID_ASK = "bid_ask"


class IntradayInterval(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"

    @property
    def minutes(self) -> int:
        return 1 if self is IntradayInterval.ONE_MINUTE else 5


class IntradayCandle(BaseModel):
    security_id: str
    market_id: str
    code: str
    interval: IntradayInterval
    session: TradingSession
    bucket_start: datetime
    bucket_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0
    turnover_amount: Decimal | None = None
    trade_count: int | None = None
    first_sequence: int | None = None
    last_sequence: int | None = None
    quote_count: int = 0
    is_final: bool = False
    data_status: DataStatus
    provider: str
    created_at: datetime
    updated_at: datetime


class ProviderCapabilities(BaseModel):
    provider_name: str
    source_type: str  # e.g., "WEBSOCKET", "POLLING", "FAKE"
    realtime_available: bool = False
    delay_seconds: int = 0
    redistribution_allowed: bool = False
    license_status: LicenseStatus = LicenseStatus.UNCONFIGURED
    configured: bool = False
    last_error: str | None = None
    subscription_hard_limit: int | None = None

    @property
    def is_live_eligible(self) -> bool:
        return (
            self.license_status == LicenseStatus.AUTHORIZED
            and self.configured
            and self.realtime_available
        )


class RealtimeQuote(BaseModel):
    security_id: str
    market_id: str  # TWSE or TPEx
    code: str

    exchange_timestamp: datetime
    received_at: datetime

    last_price: Decimal
    last_size: int = 0

    open_price: Decimal | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    previous_close: Decimal | None = None

    total_volume: int = 0
    turnover_amount: Decimal | None = None

    bid_price: Decimal | None = None
    bid_size: int | None = None
    ask_price: Decimal | None = None
    ask_size: int | None = None
    bid_prices: list[Decimal] | None = None
    bid_volumes: list[int] | None = None
    ask_prices: list[Decimal] | None = None
    ask_volumes: list[int] | None = None

    change: Decimal | None = None
    change_percent: Decimal | None = None

    session: TradingSession = TradingSession.REGULAR
    sequence: int | None = None

    data_status: DataStatus = DataStatus.LIVE
    provider: str = "UNKNOWN"
    delay_seconds: int = 0
    source_timestamp: datetime | None = None
    event_kind: RealtimeEventKind = RealtimeEventKind.UPDATE

    @property
    def composite_key(self) -> str:
        return f"{self.market_id.upper()}:{self.code}"


class RealtimeBidAsk(BaseModel):
    market_id: str
    code: str
    exchange_timestamp: datetime
    received_at: datetime
    bid_prices: list[Decimal]
    bid_volumes: list[int]
    ask_prices: list[Decimal]
    ask_volumes: list[int]
    data_status: DataStatus = DataStatus.LIVE
    provider: str = "UNKNOWN"
