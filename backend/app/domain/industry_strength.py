from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode

ALGORITHM_VERSION = "twml-industry-strength-v1"
MIN_COMPONENT_COVERAGE_THRESHOLD = Decimal("0.60")


@dataclass(frozen=True)
class StrengthComponents:
    momentum_score: Decimal | None = None
    breadth_score: Decimal | None = None
    technical_score: Decimal | None = None
    institutional_score: Decimal | None = None
    turnover_score: Decimal | None = None


@dataclass(frozen=True)
class TaxonomyStrengthSnapshot:
    id: UUID
    taxonomy_id: UUID
    taxonomy_code: str
    taxonomy_name: str
    taxonomy_type: str  # "OFFICIAL" or "CUSTOM"
    trade_date: date
    window: int
    equal_weight_return: Decimal
    market_cap_weighted_return: Decimal | None
    total_members: int
    valid_members: int
    coverage_ratio: Decimal
    advancers: int
    decliners: int
    unchanged: int
    advance_ratio: Decimal
    above_ma20_pct: Decimal
    above_ma60_pct: Decimal
    foreign_net_amount: Decimal
    investment_trust_net_amount: Decimal
    dealer_net_amount: Decimal
    margin_balance_change: Decimal
    short_balance_change: Decimal
    lending_balance_change: Decimal | None
    turnover_amount: Decimal | None
    turnover_share: Decimal | None
    turnover_momentum: Decimal | None
    components: StrengthComponents
    strength_score: Decimal | None
    component_coverage: Decimal
    rank: int | None
    algorithm_version: str
    data_status: DataStatus
    as_of: datetime


@dataclass(frozen=True)
class TaxonomyLeader:
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    return_pct: Decimal
    latest_close: Decimal | None
    foreign_net: Decimal | None
    data_status: DataStatus


@dataclass(frozen=True)
class TaxonomyStrengthDetail:
    snapshot: TaxonomyStrengthSnapshot
    leaders: list[TaxonomyLeader]
    laggards: list[TaxonomyLeader]
