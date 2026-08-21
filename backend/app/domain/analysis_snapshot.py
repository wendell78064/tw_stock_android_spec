from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode


class PromptSectionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    NO_DATA = "NO_DATA"


@dataclass(frozen=True)
class SecurityIdentitySnapshot:
    code: str
    name: str
    market: MarketCode
    security_type: str
    primary_industry: str | None
    themes: list[str]
    listing_date: date | None


@dataclass(frozen=True)
class PriceSnapshot:
    trade_date: date
    close: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume_shares: int | None
    turnover_amount: Decimal | None
    data_status: DataStatus
    as_of: datetime | None = None


@dataclass(frozen=True)
class ReturnsSnapshot:
    return_1d: Decimal | None = None
    return_5d: Decimal | None = None
    return_10d: Decimal | None = None
    return_30d: Decimal | None = None
    return_1y: Decimal | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class TechnicalSnapshotData:
    trade_date: date
    ma5: Decimal | None = None
    ma10: Decimal | None = None
    ma20: Decimal | None = None
    ma60: Decimal | None = None
    ma120: Decimal | None = None
    ma240: Decimal | None = None
    rsi: Decimal | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_hist: Decimal | None = None
    kd_k: Decimal | None = None
    kd_d: Decimal | None = None
    bollinger_upper: Decimal | None = None
    bollinger_middle: Decimal | None = None
    bollinger_lower: Decimal | None = None
    atr: Decimal | None = None
    williams_r: Decimal | None = None
    obv: Decimal | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class InstitutionalNetSnapshot:
    foreign_net_shares: int | None = None
    trust_net_shares: int | None = None
    dealer_net_shares: int | None = None
    total_net_shares: int | None = None


@dataclass(frozen=True)
class InstitutionalSnapshot:
    trade_date: date | None
    latest_day: InstitutionalNetSnapshot
    cum_5d: InstitutionalNetSnapshot
    cum_10d: InstitutionalNetSnapshot
    consecutive_foreign_days: int | None = None
    consecutive_trust_days: int | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class CreditSnapshot:
    trade_date: date | None
    margin_balance: int | None = None
    margin_change: int | None = None
    short_balance: int | None = None
    short_change: int | None = None
    short_margin_ratio: Decimal | None = None
    lending_balance: int | None = None
    lending_change: int | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class IndustryContextSnapshot:
    industry_name: str | None
    rank: int | None = None
    total_industries: int | None = None
    strength_score: Decimal | None = None
    representative_stocks: list[str] | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class MarketContextSnapshot:
    trade_date: date | None
    taiex_close: Decimal | None = None
    taiex_change_pct: Decimal | None = None
    advances_count: int | None = None
    declines_count: int | None = None
    unchanged_count: int | None = None
    institutional_spot_net: Decimal | None = None
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class DerivativesContextSnapshot:
    trade_date: date | None
    tx_close: Decimal | None = None
    foreign_futures_net_oi: int | None = None
    option_put_call_ratio: Decimal | None = None
    top10_trader_concentration_pct: Decimal | None = None
    vix_status: str = "UNAVAILABLE"
    data_status: PromptSectionStatus = PromptSectionStatus.COMPLETE


@dataclass(frozen=True)
class PortfolioPositionSnapshot:
    shares: int
    moving_average_cost: Decimal
    latest_market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    as_of: datetime | None = None


@dataclass(frozen=True)
class DataQualitySummary:
    overall_status: PromptSectionStatus
    completeness_pct: Decimal
    freshness_notes: list[str]


@dataclass(frozen=True)
class SecurityAnalysisSnapshot:
    as_of: datetime
    generated_at: datetime
    market: MarketCode
    security: SecurityIdentitySnapshot
    price: PriceSnapshot | None
    returns: ReturnsSnapshot
    technicals: TechnicalSnapshotData | None
    institutional: InstitutionalSnapshot | None
    credit: CreditSnapshot | None
    industry: IndustryContextSnapshot | None
    market_context: MarketContextSnapshot | None
    derivatives_context: DerivativesContextSnapshot | None
    portfolio_position: PortfolioPositionSnapshot | None
    data_quality: DataQualitySummary


@dataclass(frozen=True)
class ComparisonSecurityItem:
    code: str
    market: MarketCode


@dataclass(frozen=True)
class ComparisonAnalysisSnapshot:
    generated_at: datetime
    snapshots: list[SecurityAnalysisSnapshot]
    unified_market_context: MarketContextSnapshot | None
    unified_derivatives_context: DerivativesContextSnapshot | None

