from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class AuditStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NO_DATA = "NO_DATA"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    FAILED = "FAILED"


@dataclass
class SecurityMasterAudit:
    total_securities: int
    active_common_stocks: int
    twse_common_stocks: int
    tpex_common_stocks: int
    inactive_securities: int
    duplicate_count: int
    status: AuditStatus


@dataclass
class DailyPriceMarketAudit:
    market: str
    active_common_stocks: int
    expected_eligible: int
    rows_with_price: int
    trading_rows: int
    suspended_or_no_trade_rows: int
    missing_count: int
    coverage_ratio: float
    duplicate_count: int
    latest_date: date | None
    status: AuditStatus


@dataclass
class MarketSpotAudit:
    market_breadth_rows: int
    margin_trading_rows: int
    securities_lending_rows: int
    institutional_spot_rows: int
    duplicate_count: int
    status: AuditStatus


@dataclass
class DerivativesDatasetAudit:
    dataset: str
    row_count: int
    status: AuditStatus
    as_of: datetime | None = None
    note: str | None = None


@dataclass
class TechnicalsAudit:
    active_stocks: int
    snapshot_date: date | None
    snapshots_count: int
    stale_count: int
    ma240_eligible_count: int
    ma240_valid_count: int
    ma240_missing_count: int
    duplicate_count: int
    status: AuditStatus


@dataclass
class IndustryStrengthAudit:
    snapshot_date: date | None
    snapshot_count: int
    status: AuditStatus


@dataclass
class DuplicateAudit:
    duplicate_securities: int
    duplicate_daily_prices: int
    duplicate_technical_snapshots: int
    duplicate_market_spot: int
    duplicate_derivatives: int
    status: AuditStatus


@dataclass
class HistoricalGapSession:
    trade_date: date
    market: str
    expected: int
    actual: int
    coverage_ratio: float
    status: AuditStatus
    is_anomalous: bool
    reason: str | None = None


@dataclass
class HistoricalGapAudit:
    market: str
    start_date: date
    end_date: date
    total_weekdays: int
    trading_sessions: int
    holiday_sessions: int
    anomalous_sessions: int
    anomalies: list[HistoricalGapSession] = field(default_factory=list)
    status: AuditStatus = AuditStatus.COMPLETE


@dataclass
class DailyDataAuditReport:
    target_date: date
    is_trading_day: bool
    day_type: str
    security_master: SecurityMasterAudit
    twse_daily: DailyPriceMarketAudit
    tpex_daily: DailyPriceMarketAudit
    market_spot: MarketSpotAudit
    derivatives: list[DerivativesDatasetAudit]
    technicals: TechnicalsAudit
    industry_strength: IndustryStrengthAudit
    duplicates: DuplicateAudit
    overall_status: AuditStatus

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        def _serialize(val: Any) -> Any:
            if isinstance(val, date | datetime):
                return val.isoformat()
            if isinstance(val, dict):
                return {k: _serialize(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_serialize(item) for item in val]
            if isinstance(val, StrEnum):
                return str(val)
            return val

        return _serialize(data)
