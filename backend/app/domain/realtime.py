from datetime import datetime
from decimal import Decimal
from enum import Enum
from pydantic import BaseModel, Field


class LicenseStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    UNVERIFIED = "UNVERIFIED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    UNCONFIGURED = "UNCONFIGURED"


class DataStatus(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    DELAYED = "DELAYED"
    UNAVAILABLE = "UNAVAILABLE"


class TradingSession(str, Enum):
    REGULAR = "REGULAR"
    AFTER_HOURS = "AFTER_HOURS"
    UNKNOWN = "UNKNOWN"


class ProviderCapabilities(BaseModel):
    provider_name: str
    source_type: str  # e.g., "WEBSOCKET", "POLLING", "FAKE"
    realtime_available: bool = False
    delay_seconds: int = 0
    redistribution_allowed: bool = False
    license_status: LicenseStatus = LicenseStatus.UNCONFIGURED
    configured: bool = False
    last_error: str | None = None

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

    change: Decimal | None = None
    change_percent: Decimal | None = None

    session: TradingSession = TradingSession.REGULAR
    sequence: int | None = None

    data_status: DataStatus = DataStatus.LIVE
    provider: str = "UNKNOWN"
    delay_seconds: int = 0
    source_timestamp: datetime | None = None

    @property
    def composite_key(self) -> str:
        return f"{self.market_id.upper()}:{self.code}"
