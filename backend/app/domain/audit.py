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


class RepairDecisionOutcome(StrEnum):
    REPAIRABLE = "REPAIRABLE"
    NOT_PUBLISHED = "NOT_PUBLISHED"
    HOLIDAY = "HOLIDAY"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED = "UNSUPPORTED"
    SKIP = "SKIP"
    FAILED = "FAILED"


class RepairScopeType(StrEnum):
    SECURITY_DATE = "SECURITY_DATE"
    DATASET_DATE = "DATASET_DATE"
    DATE_RANGE = "DATE_RANGE"


MAX_REPAIR_RANGE_DAYS: int = 30


@dataclass(frozen=True)
class RepairScope:
    scope_type: RepairScopeType
    dataset: str
    target_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    market: str | None = None
    security_code: str | None = None

    def __post_init__(self) -> None:
        if self.scope_type == RepairScopeType.SECURITY_DATE:
            if not self.target_date or not self.market or not self.security_code:
                raise ValueError(
                    "SECURITY_DATE repair scope requires target_date, market, and security_code"
                )
        elif self.scope_type == RepairScopeType.DATASET_DATE:
            if not self.target_date:
                raise ValueError("DATASET_DATE repair scope requires target_date")
        elif self.scope_type == RepairScopeType.DATE_RANGE:
            if not self.start_date or not self.end_date:
                raise ValueError("DATE_RANGE repair scope requires start_date and end_date")
            if self.start_date > self.end_date:
                raise ValueError("start_date cannot be after end_date")
            days_span = (self.end_date - self.start_date).days + 1
            if days_span > MAX_REPAIR_RANGE_DAYS:
                raise ValueError(
                    f"DATE_RANGE span ({days_span} days) exceeds maximum allowed precision repair "
                    f"limit ({MAX_REPAIR_RANGE_DAYS} days). Broad multi-year ranges cannot qualify "
                    "for precision repair."
                )


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    dataset: str
    target_date: date
    audit_status: AuditStatus
    market: str | None = None
    security_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    missing_count: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class RepairDecision:
    finding_id: str
    outcome: RepairDecisionOutcome
    reason: str
    scope: RepairScope | None = None


@dataclass
class PrecisionRepairResult:
    finding_id: str
    decision: RepairDecision
    executed: bool
    status_before: AuditStatus
    status_after: AuditStatus
    repaired_records_inserted: int = 0
    repaired_records_updated: int = 0
    error: str | None = None
    ingestion_run_id: str | None = None
    re_audit_report: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime | None = None

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
