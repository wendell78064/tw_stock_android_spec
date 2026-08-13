from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode


class ComparisonWindow(StrEnum):
    ONE_DAY = "1D"
    FIVE_DAYS = "5D"
    TEN_DAYS = "10D"
    TWENTY_DAYS = "20D"
    SIXTY_DAYS = "60D"
    ONE_YEAR = "1Y"
    FIVE_YEARS = "5Y"


class SignalType(StrEnum):
    PRICE_OUTPERFORMANCE = "PRICE_OUTPERFORMANCE"
    PRICE_UNDERPERFORMANCE = "PRICE_UNDERPERFORMANCE"
    INSTITUTIONAL_DIVERGENCE = "INSTITUTIONAL_DIVERGENCE"
    TECHNICAL_DIVERGENCE = "TECHNICAL_DIVERGENCE"
    INDUSTRY_STRENGTH_DIVERGENCE = "INDUSTRY_STRENGTH_DIVERGENCE"
    MOMENTUM_DIVERGENCE = "MOMENTUM_DIVERGENCE"


@dataclass(frozen=True)
class ComparisonSignalConfig:
    return_diff_pct_points_threshold: Decimal = Decimal("5.0")
    rsi_diff_threshold: Decimal = Decimal("15.0")
    strength_diff_threshold: Decimal = Decimal("15.0")


@dataclass
class NormalizedPoint:
    trade_date: date
    values: dict[str, Decimal | None]  # security_code -> normalized_value


@dataclass
class SecurityMetricSummary:
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    latest_close: Decimal | None
    return_1d: Decimal | None
    return_5d: Decimal | None
    return_10d: Decimal | None
    return_20d: Decimal | None
    return_60d: Decimal | None
    return_selected_window: Decimal | None
    ma5: Decimal | None
    ma20: Decimal | None
    ma60: Decimal | None
    close_vs_ma20: Decimal | None
    close_vs_ma60: Decimal | None
    rsi14: Decimal | None
    macd_state: str | None
    kd_state: str | None
    foreign_1d_net: Decimal | None
    foreign_5d_net: Decimal | None
    foreign_10d_net: Decimal | None
    foreign_20d_net: Decimal | None
    trust_1d_net: Decimal | None
    trust_5d_net: Decimal | None
    trust_10d_net: Decimal | None
    trust_20d_net: Decimal | None
    dealer_1d_net: Decimal | None
    dealer_5d_net: Decimal | None
    margin_balance_change: Decimal | None
    short_balance_change: Decimal | None
    lending_balance_change: Decimal | None
    industry_name: str | None
    themes: list[str]
    industry_strength_score: Decimal | None
    industry_strength_rank: int | None
    selected_set_return_rank: int | None = None
    selected_set_rsi_rank: int | None = None
    selected_set_foreign_rank: int | None = None
    selected_set_strength_rank: int | None = None
    data_status: DataStatus = DataStatus.FINAL


@dataclass
class ObjectiveSignal:
    signal_type: SignalType
    subject_code: str
    comparator_code: str
    headline: str
    details: str
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    window: ComparisonWindow
    requested_start: date
    effective_start: date
    effective_end: date
    securities: list[SecurityMetricSummary]
    normalized_series: list[NormalizedPoint]
    objective_signals: list[ObjectiveSignal]
    coverage: Decimal
    data_status: DataStatus
    as_of: datetime
