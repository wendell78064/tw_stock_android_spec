from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.industry import IndustryInfo, MemberSecurity, ThemeInfo
from app.domain.industry_strength import TaxonomyLeader, TaxonomyStrengthSnapshot
from app.domain.market_data import DataStatus
from app.domain.pricing import Candle, PriceBasis, TechnicalSnapshot
from app.domain.security import MarketCode, Security, SecurityStatus, SecurityType, ThemeRef


class MetaResponse(BaseModel):
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source: str


class ThemeRefResponse(BaseModel):
    id: UUID
    code: str
    name: str

    @classmethod
    def from_domain(cls, ref: ThemeRef) -> "ThemeRefResponse":
        return cls(id=ref.id, code=ref.code, name=ref.name)


class SecurityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    market: MarketCode
    security_type: SecurityType
    status: SecurityStatus
    primary_industry: str | None
    listing_date: date | None
    is_active: bool
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source: str
    themes: list[ThemeRefResponse] = []

    @classmethod
    def from_domain(cls, security: Security) -> "SecurityResponse":
        return cls(
            id=security.id,
            code=security.code,
            name=security.name,
            market=security.market,
            security_type=security.security_type,
            status=security.status,
            primary_industry=security.primary_industry,
            listing_date=security.listing_date,
            is_active=security.is_active,
            as_of=security.as_of,
            received_at=security.received_at,
            data_status=security.data_status,
            source=security.source_code,
            themes=[ThemeRefResponse.from_domain(t) for t in security.themes],
        )


class SecuritySearchItem(BaseModel):
    id: UUID
    code: str
    name: str
    market: MarketCode
    security_type: SecurityType
    primary_industry: str | None
    is_active: bool
    as_of: datetime
    received_at: datetime
    data_status: DataStatus

    @classmethod
    def from_domain(cls, security: Security) -> "SecuritySearchItem":
        return cls(
            **SecurityResponse.from_domain(security).model_dump(
                exclude={"status", "listing_date", "source", "themes"}
            )
        )



class SecurityEnvelope(BaseModel):
    data: SecurityResponse
    meta: MetaResponse


class SecuritySearchEnvelope(BaseModel):
    data: list[SecuritySearchItem]
    meta: MetaResponse


def meta_for(securities: list[Security]) -> MetaResponse:
    return MetaResponse(
        as_of=max(item.as_of for item in securities),
        received_at=max(item.received_at for item in securities),
        data_status=securities[0].data_status
        if len({item.data_status for item in securities}) == 1
        else DataStatus.PARTIAL,
        source=",".join(sorted({item.source_code for item in securities})),
    )


class CandleResponse(BaseModel):
    time: datetime
    open: str
    high: str
    low: str
    close: str
    volume_shares: int | None
    turnover_amount: str | None

    @classmethod
    def from_domain(cls, candle: Candle) -> "CandleResponse":
        from datetime import time
        from zoneinfo import ZoneInfo

        return cls(
            time=datetime.combine(candle.trade_date, time(), ZoneInfo("Asia/Taipei")),
            open=str(candle.open),
            high=str(candle.high),
            low=str(candle.low),
            close=str(candle.close),
            volume_shares=candle.volume_shares,
            turnover_amount=None if candle.turnover_amount is None else str(candle.turnover_amount),
        )


class CandleSeriesEnvelope(BaseModel):
    data: list[CandleResponse]
    meta: MetaResponse
    interval: str
    adjustment: PriceBasis
    display_note: str | None = None


class IndicatorValueResponse(BaseModel):
    name: str
    parameters: dict[str, int | str]
    value: str | None


class TechnicalPointResponse(BaseModel):
    trade_date: date
    price_basis: PriceBasis
    algorithm_version: str
    indicators: list[IndicatorValueResponse]
    as_of: datetime
    data_status: DataStatus

    @classmethod
    def from_domain(
        cls, snapshot: TechnicalSnapshot, selected: set[str] | None
    ) -> "TechnicalPointResponse":
        parameters = snapshot.parameters or {
            "MACD": {"fast": 12, "slow": 26, "signal": 9},
            "KD_K": {"period": 9, "smoothing": 3},
            "KD_D": {"period": 9, "smoothing": 3},
            "BBANDS_UPPER": {"period": 20, "stddev": "2"},
            "BBANDS_MIDDLE": {"period": 20, "stddev": "2"},
            "BBANDS_LOWER": {"period": 20, "stddev": "2"},
        }
        items = [
            IndicatorValueResponse(
                name=name,
                parameters=parameters.get(name, {}),
                value=None if value is None else str(value),
            )
            for name, value in snapshot.values.items()
            if selected is None or name in selected
        ]
        return cls(
            trade_date=snapshot.trade_date,
            price_basis=snapshot.price_basis,
            algorithm_version=snapshot.algorithm_version,
            indicators=items,
            as_of=snapshot.as_of,
            data_status=snapshot.data_status,
        )


class IndustryResponse(BaseModel):
    id: UUID
    code: str
    name: str
    classification_source: str
    member_count: int

    @classmethod
    def from_domain(cls, info: IndustryInfo) -> "IndustryResponse":
        return cls(
            id=info.id,
            code=info.code,
            name=info.name,
            classification_source=info.classification_source,
            member_count=info.member_count,
        )


class IndustryListEnvelope(BaseModel):
    data: list[IndustryResponse]
    meta: MetaResponse


class IndustryEnvelope(BaseModel):
    data: IndustryResponse
    meta: MetaResponse


class ThemeResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None
    classification_type: str
    member_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_domain(cls, info: ThemeInfo) -> "ThemeResponse":
        return cls(
            id=info.id,
            code=info.code,
            name=info.name,
            description=info.description,
            classification_type=info.classification_type,
            member_count=info.member_count,
            created_at=info.created_at,
            updated_at=info.updated_at,
        )


class ThemeListEnvelope(BaseModel):
    data: list[ThemeResponse]
    meta: MetaResponse


class ThemeEnvelope(BaseModel):
    data: ThemeResponse
    meta: MetaResponse


class MemberSecurityResponse(BaseModel):
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    security_type: SecurityType
    is_active: bool
    close: str | None
    change: str | None
    change_percent: str | None
    as_of: datetime | None
    data_status: DataStatus

    @classmethod
    def from_domain(cls, mem: MemberSecurity) -> "MemberSecurityResponse":
        return cls(
            security_id=mem.security_id,
            code=mem.code,
            name=mem.name,
            market=mem.market,
            security_type=mem.security_type,
            is_active=mem.is_active,
            close=str(mem.close) if mem.close is not None else None,
            change=str(mem.change) if mem.change is not None else None,
            change_percent=str(mem.change_percent) if mem.change_percent is not None else None,
            as_of=mem.as_of,
            data_status=mem.data_status,
        )


class IndustrySecuritiesEnvelope(BaseModel):
    data: list[MemberSecurityResponse]
    meta: MetaResponse


class ThemeSecuritiesEnvelope(BaseModel):
    data: list[MemberSecurityResponse]
    meta: MetaResponse


class CreateThemeInput(BaseModel):
    code: str
    name: str
    description: str | None = None
    classification_type: str = "CUSTOM"


class UpdateThemeInput(BaseModel):
    name: str | None = None
    description: str | None = None


class AddThemeSecurityInput(BaseModel):
    security_id: UUID



class TechnicalSeriesEnvelope(BaseModel):
    data: list[TechnicalPointResponse]
    meta: MetaResponse


class StrengthComponentsResponse(BaseModel):
    momentum_score: str | None = None
    breadth_score: str | None = None
    technical_score: str | None = None
    institutional_score: str | None = None
    turnover_score: str | None = None


class TaxonomyStrengthResponse(BaseModel):
    id: UUID
    taxonomy_id: UUID
    taxonomy_code: str
    taxonomy_name: str
    taxonomy_type: str
    trade_date: date
    window: int
    equal_weight_return: str
    market_cap_weighted_return: str | None = None
    total_members: int
    valid_members: int
    coverage_ratio: str
    advancers: int
    decliners: int
    unchanged: int
    advance_ratio: str
    above_ma20_pct: str
    above_ma60_pct: str
    foreign_net_amount: str
    investment_trust_net_amount: str
    dealer_net_amount: str
    margin_balance_change: str
    short_balance_change: str
    lending_balance_change: str | None = None
    turnover_amount: str | None = None
    turnover_share: str | None = None
    turnover_momentum: str | None = None
    components: StrengthComponentsResponse
    strength_score: str | None = None
    component_coverage: str
    rank: int | None = None
    algorithm_version: str
    data_status: DataStatus
    as_of: datetime

    @classmethod
    def from_domain(cls, snap: TaxonomyStrengthSnapshot) -> "TaxonomyStrengthResponse":
        c = snap.components
        return cls(
            id=snap.id,
            taxonomy_id=snap.taxonomy_id,
            taxonomy_code=snap.taxonomy_code,
            taxonomy_name=snap.taxonomy_name,
            taxonomy_type=snap.taxonomy_type,
            trade_date=snap.trade_date,
            window=snap.window,
            equal_weight_return=str(snap.equal_weight_return),
            market_cap_weighted_return=(
                str(snap.market_cap_weighted_return)
                if snap.market_cap_weighted_return is not None
                else None
            ),
            total_members=snap.total_members,
            valid_members=snap.valid_members,
            coverage_ratio=str(snap.coverage_ratio),
            advancers=snap.advancers,
            decliners=snap.decliners,
            unchanged=snap.unchanged,
            advance_ratio=str(snap.advance_ratio),
            above_ma20_pct=str(snap.above_ma20_pct),
            above_ma60_pct=str(snap.above_ma60_pct),
            foreign_net_amount=str(snap.foreign_net_amount),
            investment_trust_net_amount=str(snap.investment_trust_net_amount),
            dealer_net_amount=str(snap.dealer_net_amount),
            margin_balance_change=str(snap.margin_balance_change),
            short_balance_change=str(snap.short_balance_change),
            lending_balance_change=(
                str(snap.lending_balance_change)
                if snap.lending_balance_change is not None
                else None
            ),
            turnover_amount=(
                str(snap.turnover_amount)
                if snap.turnover_amount is not None
                else None
            ),
            turnover_share=(
                str(snap.turnover_share)
                if snap.turnover_share is not None
                else None
            ),
            turnover_momentum=(
                str(snap.turnover_momentum)
                if snap.turnover_momentum is not None
                else None
            ),
            components=StrengthComponentsResponse(
                momentum_score=str(c.momentum_score) if c.momentum_score is not None else None,
                breadth_score=str(c.breadth_score) if c.breadth_score is not None else None,
                technical_score=str(c.technical_score) if c.technical_score is not None else None,
                institutional_score=(
                    str(c.institutional_score) if c.institutional_score is not None else None
                ),
                turnover_score=str(c.turnover_score) if c.turnover_score is not None else None,
            ),
            strength_score=str(snap.strength_score) if snap.strength_score is not None else None,
            component_coverage=str(snap.component_coverage),
            rank=snap.rank,
            algorithm_version=snap.algorithm_version,
            data_status=snap.data_status,
            as_of=snap.as_of,
        )


class TaxonomyLeaderResponse(BaseModel):
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    return_pct: str
    latest_close: str | None = None
    foreign_net: str | None = None
    data_status: DataStatus

    @classmethod
    def from_domain(cls, leader: TaxonomyLeader) -> "TaxonomyLeaderResponse":
        return cls(
            security_id=leader.security_id,
            code=leader.code,
            name=leader.name,
            market=leader.market,
            return_pct=str(leader.return_pct),
            latest_close=str(leader.latest_close) if leader.latest_close is not None else None,
            foreign_net=str(leader.foreign_net) if leader.foreign_net is not None else None,
            data_status=leader.data_status,
        )


class TaxonomyStrengthDetailResponse(BaseModel):
    snapshot: TaxonomyStrengthResponse
    leaders: list[TaxonomyLeaderResponse]
    laggards: list[TaxonomyLeaderResponse]


class TaxonomyStrengthListEnvelope(BaseModel):
    data: list[TaxonomyStrengthResponse]
    meta: MetaResponse


class TaxonomyStrengthDetailEnvelope(BaseModel):
    data: TaxonomyStrengthDetailResponse
    meta: MetaResponse


class ScreenerFieldMetaSchema(BaseModel):
    field_id: str
    label: str
    category: str
    value_type: str
    allowed_operators: list[str]
    unit: str | None = None
    supported_windows: list[int] | None = None


class ScreenerFieldsEnvelope(BaseModel):
    data: list[ScreenerFieldMetaSchema]
    meta: MetaResponse


class RunScreenerInput(BaseModel):
    expression: dict[str, Any]
    trade_date: date | None = None
    sort_field: str = "code"
    sort_direction: str = "ASC"
    limit: int = 50
    offset: int = 0


class CreateSavedScreenerInput(BaseModel):
    name: str
    description: str | None = None
    expression: dict[str, Any]
    sort_field: str = "code"
    sort_direction: str = "ASC"


class UpdateSavedScreenerInput(BaseModel):
    name: str | None = None
    description: str | None = None
    expression: dict[str, Any] | None = None
    sort_field: str | None = None
    sort_direction: str | None = None


class ScreenerResultSecuritySchema(BaseModel):
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    industry_name: str | None = None
    themes: list[str] = []
    close: str | None = None
    return_pct: str | None = None
    matched_conditions: list[str] = []
    extra_metrics: dict[str, Any] = {}
    data_status: DataStatus


class ScreenerResultEnvelope(BaseModel):
    data: list[ScreenerResultSecuritySchema]
    total_count: int
    trade_date: date
    meta: MetaResponse


class SavedScreenerEnvelope(BaseModel):
    data: dict[str, Any]
    meta: MetaResponse


class SavedScreenerListEnvelope(BaseModel):
    data: list[dict[str, Any]]
    meta: MetaResponse


class SecurityTargetInput(BaseModel):
    code: str
    market: MarketCode


class RunComparisonInput(BaseModel):
    targets: list[SecurityTargetInput]
    window: str = "20D"
    trade_date: date | None = None


class NormalizedPointSchema(BaseModel):
    trade_date: date
    values: dict[str, str | None]


class ObjectiveSignalSchema(BaseModel):
    signal_type: str
    subject_code: str
    comparator_code: str
    headline: str
    details: str
    metrics: dict[str, Any] = {}


class ComparisonSecuritySummarySchema(BaseModel):
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    latest_close: str | None = None
    return_1d: str | None = None
    return_5d: str | None = None
    return_10d: str | None = None
    return_20d: str | None = None
    return_60d: str | None = None
    return_selected_window: str | None = None
    ma5: str | None = None
    ma20: str | None = None
    ma60: str | None = None
    close_vs_ma20: str | None = None
    close_vs_ma60: str | None = None
    rsi14: str | None = None
    macd_state: str | None = None
    kd_state: str | None = None
    foreign_1d_net: str | None = None
    foreign_5d_net: str | None = None
    trust_1d_net: str | None = None
    trust_5d_net: str | None = None
    dealer_1d_net: str | None = None
    dealer_5d_net: str | None = None
    margin_balance_change: str | None = None
    short_balance_change: str | None = None
    lending_balance_change: str | None = None
    industry_name: str | None = None
    themes: list[str] = []
    industry_strength_score: str | None = None
    industry_strength_rank: int | None = None
    selected_set_return_rank: int | None = None
    selected_set_rsi_rank: int | None = None
    selected_set_foreign_rank: int | None = None
    data_status: DataStatus


class ComparisonResultSchema(BaseModel):
    window: str
    requested_start: date
    effective_start: date
    effective_end: date
    securities: list[ComparisonSecuritySummarySchema]
    normalized_series: list[NormalizedPointSchema]
    objective_signals: list[ObjectiveSignalSchema]
    coverage: str


class ComparisonEnvelope(BaseModel):
    data: ComparisonResultSchema
    meta: MetaResponse


class AnalysisPromptResponse(BaseModel):
    security: SecurityResponse
    as_of: datetime
    generated_at: datetime
    prompt: str
    character_count: int
    data_status: DataStatus
    portfolio_included: bool


class AnalysisPromptEnvelope(BaseModel):
    data: AnalysisPromptResponse
    meta: MetaResponse


class ComparisonAnalysisSecurityItem(BaseModel):
    code: str
    market: MarketCode


class ComparisonAnalysisPromptInput(BaseModel):
    securities: list[ComparisonAnalysisSecurityItem]


class ComparisonAnalysisPromptResponse(BaseModel):
    securities: list[SecurityResponse]
    generated_at: datetime
    prompt: str
    character_count: int
    data_status: DataStatus


class ComparisonAnalysisPromptEnvelope(BaseModel):
    data: ComparisonAnalysisPromptResponse
    meta: MetaResponse

