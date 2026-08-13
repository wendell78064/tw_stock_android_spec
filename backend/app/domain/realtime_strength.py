from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.realtime import DataStatus

REALTIME_STRENGTH_VERSION = "twml-industry-realtime-strength-v1"


class RealtimeTaxonomyType(StrEnum):
    INDUSTRY = "INDUSTRY"
    THEME = "THEME"


class RealtimeStrengthComponents(BaseModel):
    momentum: Decimal | None = None
    breadth: Decimal | None = None
    technical: Decimal | None = None
    turnover: Decimal | None = None


class RealtimeLeader(BaseModel):
    security_id: str
    market: str
    code: str
    name: str
    last_price: Decimal
    change: Decimal
    change_percent: Decimal
    data_status: DataStatus


class RealtimeMarketSnapshot(BaseModel):
    market_id: str
    as_of: datetime
    exchange_timestamp: datetime
    total_members: int
    valid_members: int
    quoted_members: int
    coverage_ratio: Decimal
    advancers: int
    decliners: int
    unchanged: int
    advance_ratio: Decimal
    decline_ratio: Decimal
    turnover_amount: Decimal | None = None
    live_count: int
    stale_count: int
    unavailable_count: int
    data_status: DataStatus
    provider: str
    source_type: str
    algorithm_version: str = REALTIME_STRENGTH_VERSION


class RealtimeTaxonomySnapshot(BaseModel):
    taxonomy_type: RealtimeTaxonomyType
    taxonomy_id: str
    code: str
    name: str
    as_of: datetime
    total_members: int
    valid_members: int
    quoted_members: int
    coverage_ratio: Decimal
    equal_weight_return: Decimal | None
    advancers: int
    decliners: int
    unchanged: int
    advance_ratio: Decimal | None
    turnover_amount: Decimal | None = None
    turnover_share: Decimal | None = None
    above_ma20_pct_realtime: Decimal | None = None
    above_ma60_pct_realtime: Decimal | None = None
    components: RealtimeStrengthComponents = Field(default_factory=RealtimeStrengthComponents)
    realtime_strength_score: Decimal | None = None
    component_coverage: Decimal = Decimal("0")
    rank: int | None = None
    leaders: list[RealtimeLeader] = Field(default_factory=list)
    laggards: list[RealtimeLeader] = Field(default_factory=list)
    data_status: DataStatus
    provider: str
    source_type: str
    algorithm_version: str = REALTIME_STRENGTH_VERSION
