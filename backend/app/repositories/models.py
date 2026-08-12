from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.market_data import DataStatus


class Base(DeclarativeBase):
    pass


class PortfolioModel(Base):
    __tablename__ = "portfolios"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80))
    base_currency: Mapped[str] = mapped_column(String(8), default="TWD")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PortfolioTransactionModel(Base):
    __tablename__ = "portfolio_transactions"
    __table_args__ = (
        Index("portfolio_transactions_portfolio_executed_idx", "portfolio_id", "executed_at"),
        Index(
            "portfolio_transactions_security_executed_idx",
            "portfolio_id",
            "security_id",
            "executed_at",
        ),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    portfolio_id: Mapped[UUID] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"))
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id"))
    side: Mapped[str] = mapped_column(String(8))
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quantity_shares: Mapped[int] = mapped_column(BigInteger)
    price: Mapped[object] = mapped_column(Numeric(24, 8))
    fee: Mapped[object] = mapped_column(Numeric(24, 8))
    lot_type: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WatchlistModel(Base):
    __tablename__ = "watchlists"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WatchlistItemModel(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("watchlist_id", "security_id"),
        Index("watchlist_items_order_idx", "watchlist_id", "sort_order"),
        Index("watchlist_items_security_idx", "security_id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    watchlist_id: Mapped[UUID] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id"))
    sort_order: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(500))
    target_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    stop_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    add_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertRuleModel(Base):
    __tablename__ = "alert_rules"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120))
    rule_type: Mapped[str] = mapped_column(String(40))
    scope_type: Mapped[str] = mapped_column(String(16))
    security_id: Mapped[UUID | None] = mapped_column(ForeignKey("securities.id"))
    portfolio_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("portfolios.id", ondelete="CASCADE")
    )
    watchlist_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE")
    )
    ma_period: Mapped[int | None] = mapped_column(Integer)
    threshold_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    threshold_percent: Mapped[object | None] = mapped_column(Numeric(10, 4))
    consecutive_days: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer)
    daily_limit: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertEventModel(Base):
    __tablename__ = "alert_events"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    alert_rule_id: Mapped[UUID] = mapped_column(ForeignKey("alert_rules.id", ondelete="CASCADE"))
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id"))
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    trade_date: Mapped[date] = mapped_column(Date)
    event_type: Mapped[str] = mapped_column(String(40))
    trigger_price: Mapped[object] = mapped_column(Numeric(24, 8))
    reference_value: Mapped[object] = mapped_column(Numeric(24, 8))
    reference_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(String(500))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    notification_eligible: Mapped[bool] = mapped_column(Boolean)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AlertEvaluationRunModel(Base):
    __tablename__ = "alert_evaluation_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_trade_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))
    rules_evaluated: Mapped[int] = mapped_column(Integer)
    securities_evaluated: Mapped[int] = mapped_column(Integer)
    events_created: Mapped[int] = mapped_column(Integer)
    errors: Mapped[int] = mapped_column(Integer)
    run_metadata: Mapped[str | None] = mapped_column(Text)


class IngestionRunModel(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(32))
    dataset: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


class MarketModel(Base):
    __tablename__ = "markets"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Taipei")


class IndustryModel(Base):
    __tablename__ = "industries"
    __table_args__ = (UniqueConstraint("classification_source", "code"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    classification_source: Mapped[str] = mapped_column(String(32))


class SecurityModel(Base):
    __tablename__ = "securities"
    __table_args__ = (UniqueConstraint("market_id", "code"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id: Mapped[UUID] = mapped_column(ForeignKey("markets.id"))
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    security_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    listing_date: Mapped[date | None] = mapped_column(Date)
    delisting_date: Mapped[date | None] = mapped_column(Date)
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityIndustryModel(Base):
    __tablename__ = "security_industries"
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True
    )
    industry_id: Mapped[UUID] = mapped_column(
        ForeignKey("industries.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class ThemeModel(Base):
    __tablename__ = "themes"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(500))
    classification_type: Mapped[str] = mapped_column(String(32), default="CUSTOM")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SecurityThemeModel(Base):
    __tablename__ = "security_themes"
    security_id: Mapped[UUID] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), primary_key=True
    )
    theme_id: Mapped[UUID] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TaxonomyStrengthSnapshotModel(Base):
    __tablename__ = "taxonomy_strength_snapshots"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    industry_id: Mapped[UUID | None] = mapped_column(ForeignKey("industries.id", ondelete="CASCADE"))
    theme_id: Mapped[UUID | None] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    window: Mapped[int] = mapped_column(Integer)
    equal_weight_return: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    market_cap_weighted_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    total_members: Mapped[int] = mapped_column(Integer)
    valid_members: Mapped[int] = mapped_column(Integer)
    coverage_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    advancers: Mapped[int] = mapped_column(Integer)
    decliners: Mapped[int] = mapped_column(Integer)
    unchanged: Mapped[int] = mapped_column(Integer)
    advance_ratio: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    above_ma20_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    above_ma60_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    foreign_net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    investment_trust_net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    dealer_net_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    margin_balance_change: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    short_balance_change: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    lending_balance_change: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    turnover_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    turnover_share: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    turnover_momentum: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    momentum_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    breadth_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    technical_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    institutional_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    turnover_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    strength_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    component_coverage: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    rank: Mapped[int | None] = mapped_column(Integer)
    algorithm_version: Mapped[str] = mapped_column(String(64), default="twml-industry-strength-v1")
    data_status: Mapped[str] = mapped_column(String(32), default="FINAL")
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))



class DailyPriceModel(Base):
    __tablename__ = "daily_prices"
    __table_args__ = (UniqueConstraint("security_id", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[object | None] = mapped_column(Numeric(24, 8))
    high: Mapped[object | None] = mapped_column(Numeric(24, 8))
    low: Mapped[object | None] = mapped_column(Numeric(24, 8))
    close: Mapped[object | None] = mapped_column(Numeric(24, 8))
    adjusted_open: Mapped[object | None] = mapped_column(Numeric(24, 8))
    adjusted_high: Mapped[object | None] = mapped_column(Numeric(24, 8))
    adjusted_low: Mapped[object | None] = mapped_column(Numeric(24, 8))
    adjusted_close: Mapped[object | None] = mapped_column(Numeric(24, 8))
    volume_shares: Mapped[int | None] = mapped_column(BigInteger)
    turnover_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    missing_reason: Mapped[str | None] = mapped_column(String(128))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class TechnicalSnapshotModel(Base):
    __tablename__ = "technical_snapshots"
    __table_args__ = (UniqueConstraint("security_id", "trade_date", "price_basis"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    price_basis: Mapped[str] = mapped_column(String(16))
    ma5: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ma10: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ma20: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ma60: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ma120: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ma240: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ema12: Mapped[object | None] = mapped_column(Numeric(24, 8))
    ema26: Mapped[object | None] = mapped_column(Numeric(24, 8))
    rsi14: Mapped[object | None] = mapped_column(Numeric(24, 8))
    macd: Mapped[object | None] = mapped_column(Numeric(24, 8))
    macd_signal: Mapped[object | None] = mapped_column(Numeric(24, 8))
    macd_histogram: Mapped[object | None] = mapped_column(Numeric(24, 8))
    kd_k: Mapped[object | None] = mapped_column(Numeric(24, 8))
    kd_d: Mapped[object | None] = mapped_column(Numeric(24, 8))
    atr14: Mapped[object | None] = mapped_column(Numeric(24, 8))
    obv: Mapped[object | None] = mapped_column(Numeric(28, 4))
    bollinger_upper: Mapped[object | None] = mapped_column(Numeric(24, 8))
    bollinger_middle: Mapped[object | None] = mapped_column(Numeric(24, 8))
    bollinger_lower: Mapped[object | None] = mapped_column(Numeric(24, 8))
    williams_r: Mapped[object | None] = mapped_column(Numeric(24, 8))
    algorithm_version: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))


class MarketIndexModel(Base):
    __tablename__ = "market_indexes"
    __table_args__ = (UniqueConstraint("market_code", "code"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80))
    market_code: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketIndexDailyModel(Base):
    __tablename__ = "market_index_daily"
    __table_args__ = (UniqueConstraint("index_id", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    index_id: Mapped[UUID] = mapped_column(ForeignKey("market_indexes.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[object | None] = mapped_column(Numeric(24, 8))
    high: Mapped[object | None] = mapped_column(Numeric(24, 8))
    low: Mapped[object | None] = mapped_column(Numeric(24, 8))
    close: Mapped[object | None] = mapped_column(Numeric(24, 8))
    change: Mapped[object | None] = mapped_column(Numeric(24, 8))
    change_percent: Mapped[object | None] = mapped_column(Numeric(16, 8))
    turnover_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class MarketBreadthModel(Base):
    __tablename__ = "market_breadth"
    __table_args__ = (UniqueConstraint("market_code", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    market_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    advancers: Mapped[int | None] = mapped_column(Integer)
    decliners: Mapped[int | None] = mapped_column(Integer)
    unchanged: Mapped[int | None] = mapped_column(Integer)
    limit_up: Mapped[int | None] = mapped_column(Integer)
    limit_down: Mapped[int | None] = mapped_column(Integer)
    total_traded: Mapped[int | None] = mapped_column(Integer)
    turnover_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class MarketInstitutionalSpotModel(Base):
    __tablename__ = "market_institutional_spot"
    __table_args__ = (
        UniqueConstraint("market_code", "trade_date", "institution_type", "dealer_subtype"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    market_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    institution_type: Mapped[str] = mapped_column(String(32))
    dealer_subtype: Mapped[str] = mapped_column(String(24), default="NONE")
    buy_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    sell_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    net_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class InstitutionSpotTradingModel(Base):
    __tablename__ = "institution_spot_trading"
    __table_args__ = (
        UniqueConstraint("security_id", "trade_date", "institution_type", "dealer_subtype"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    institution_type: Mapped[str] = mapped_column(String(32))
    dealer_subtype: Mapped[str] = mapped_column(String(24), default="NONE")
    buy_shares: Mapped[int | None] = mapped_column(BigInteger)
    sell_shares: Mapped[int | None] = mapped_column(BigInteger)
    net_shares: Mapped[int | None] = mapped_column(BigInteger)
    buy_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    sell_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    net_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class MarketMarginTradingModel(Base):
    __tablename__ = "market_margin_trading"
    __table_args__ = (UniqueConstraint("market_code", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    market_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    margin_buy: Mapped[int | None] = mapped_column(BigInteger)
    margin_sell: Mapped[int | None] = mapped_column(BigInteger)
    margin_cash_repayment: Mapped[int | None] = mapped_column(BigInteger)
    margin_balance: Mapped[int | None] = mapped_column(BigInteger)
    margin_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    short_sell: Mapped[int | None] = mapped_column(BigInteger)
    short_cover: Mapped[int | None] = mapped_column(BigInteger)
    short_stock_repayment: Mapped[int | None] = mapped_column(BigInteger)
    short_balance: Mapped[int | None] = mapped_column(BigInteger)
    short_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    short_margin_ratio: Mapped[object | None] = mapped_column(Numeric(16, 8))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class MarginTradingModel(Base):
    __tablename__ = "margin_trading"
    __table_args__ = (UniqueConstraint("security_id", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    margin_buy: Mapped[int | None] = mapped_column(BigInteger)
    margin_sell: Mapped[int | None] = mapped_column(BigInteger)
    margin_cash_repayment: Mapped[int | None] = mapped_column(BigInteger)
    margin_balance: Mapped[int | None] = mapped_column(BigInteger)
    margin_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    short_sell: Mapped[int | None] = mapped_column(BigInteger)
    short_cover: Mapped[int | None] = mapped_column(BigInteger)
    short_stock_repayment: Mapped[int | None] = mapped_column(BigInteger)
    short_balance: Mapped[int | None] = mapped_column(BigInteger)
    short_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    short_margin_ratio: Mapped[object | None] = mapped_column(Numeric(16, 8))
    margin_utilization: Mapped[object | None] = mapped_column(Numeric(16, 8))
    short_utilization: Mapped[object | None] = mapped_column(Numeric(16, 8))
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class MarketSecuritiesLendingModel(Base):
    __tablename__ = "market_securities_lending"
    __table_args__ = (UniqueConstraint("market_code", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    market_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    lending_sell: Mapped[int | None] = mapped_column(BigInteger)
    lending_return: Mapped[int | None] = mapped_column(BigInteger)
    lending_balance: Mapped[int | None] = mapped_column(BigInteger)
    lending_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class SecuritiesLendingModel(Base):
    __tablename__ = "securities_lending"
    __table_args__ = (UniqueConstraint("security_id", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    security_id: Mapped[UUID] = mapped_column(ForeignKey("securities.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    lending_sell: Mapped[int | None] = mapped_column(BigInteger)
    lending_return: Mapped[int | None] = mapped_column(BigInteger)
    lending_balance: Mapped[int | None] = mapped_column(BigInteger)
    lending_balance_change: Mapped[int | None] = mapped_column(BigInteger)
    source_code: Mapped[str] = mapped_column(String(32))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class FuturesProductModel(Base):
    __tablename__ = "futures_products"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    contract_multiplier: Mapped[object] = mapped_column(Numeric(24, 8))
    currency: Mapped[str] = mapped_column(String(8))
    session_type: Mapped[str] = mapped_column(String(24))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class FuturesContractModel(Base):
    __tablename__ = "futures_contracts"
    __table_args__ = (UniqueConstraint("product_id", "contract_code"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("futures_products.id", ondelete="CASCADE"))
    contract_code: Mapped[str] = mapped_column(String(24))
    contract_month: Mapped[str] = mapped_column(String(12))
    expiry_date: Mapped[date] = mapped_column(Date)
    last_trade_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean)


class FuturesDailyPriceModel(Base):
    __tablename__ = "futures_daily_prices"
    __table_args__ = (UniqueConstraint("contract_id", "trade_date", "session_type"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id: Mapped[UUID] = mapped_column(
        ForeignKey("futures_contracts.id", ondelete="CASCADE")
    )
    trade_date: Mapped[date] = mapped_column(Date)
    session_type: Mapped[str] = mapped_column(String(24))
    open: Mapped[object | None] = mapped_column(Numeric(24, 8))
    high: Mapped[object | None] = mapped_column(Numeric(24, 8))
    low: Mapped[object | None] = mapped_column(Numeric(24, 8))
    close: Mapped[object | None] = mapped_column(Numeric(24, 8))
    settlement_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    change: Mapped[object | None] = mapped_column(Numeric(24, 8))
    change_percent: Mapped[object | None] = mapped_column(Numeric(16, 8))
    volume: Mapped[int | None] = mapped_column(BigInteger)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class InstitutionFuturesPositionModel(Base):
    __tablename__ = "institution_futures_positions"
    __table_args__ = (UniqueConstraint("product_id", "trade_date", "institution_type"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("futures_products.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    institution_type: Mapped[str] = mapped_column(String(32))
    long_volume: Mapped[int | None] = mapped_column(BigInteger)
    short_volume: Mapped[int | None] = mapped_column(BigInteger)
    net_volume: Mapped[int | None] = mapped_column(BigInteger)
    long_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    short_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    net_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    long_oi: Mapped[int | None] = mapped_column(BigInteger)
    short_oi: Mapped[int | None] = mapped_column(BigInteger)
    net_oi: Mapped[int | None] = mapped_column(BigInteger)
    long_oi_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    short_oi_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    net_oi_amount: Mapped[object | None] = mapped_column(Numeric(28, 4))
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class TraderConcentrationModel(Base):
    __tablename__ = "trader_concentration"
    __table_args__ = (
        UniqueConstraint("product_id", "trade_date", "contract_scope", "side", "top_n"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("futures_products.id", ondelete="CASCADE"))
    trade_date: Mapped[date] = mapped_column(Date)
    contract_scope: Mapped[str] = mapped_column(String(16))
    side: Mapped[str] = mapped_column(String(8))
    top_n: Mapped[int] = mapped_column(Integer)
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    market_open_interest: Mapped[int | None] = mapped_column(BigInteger)
    concentration_ratio: Mapped[object | None] = mapped_column(Numeric(16, 8))
    specific_institution_oi: Mapped[int | None] = mapped_column(BigInteger)
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class OptionPutCallRatioModel(Base):
    __tablename__ = "option_put_call_ratios"
    __table_args__ = (UniqueConstraint("product_code", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_code: Mapped[str] = mapped_column(String(16))
    trade_date: Mapped[date] = mapped_column(Date)
    put_volume: Mapped[int | None] = mapped_column(BigInteger)
    call_volume: Mapped[int | None] = mapped_column(BigInteger)
    volume_put_call_ratio: Mapped[object | None] = mapped_column(Numeric(16, 8))
    put_open_interest: Mapped[int | None] = mapped_column(BigInteger)
    call_open_interest: Mapped[int | None] = mapped_column(BigInteger)
    oi_put_call_ratio: Mapped[object | None] = mapped_column(Numeric(16, 8))
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class OptionStrikeOpenInterestModel(Base):
    __tablename__ = "option_strike_open_interest"
    __table_args__ = (
        UniqueConstraint("product_code", "expiry", "trade_date", "option_type", "strike"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    product_code: Mapped[str] = mapped_column(String(16))
    expiry: Mapped[str] = mapped_column(String(12))
    trade_date: Mapped[date] = mapped_column(Date)
    option_type: Mapped[str] = mapped_column(String(8))
    strike: Mapped[object] = mapped_column(Numeric(24, 8))
    open_interest: Mapped[int | None] = mapped_column(BigInteger)
    volume: Mapped[int | None] = mapped_column(BigInteger)
    settlement_price: Mapped[object | None] = mapped_column(Numeric(24, 8))
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))


class VolatilityIndexModel(Base):
    __tablename__ = "volatility_indexes"
    __table_args__ = (UniqueConstraint("code", "trade_date"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(24))
    trade_date: Mapped[date] = mapped_column(Date)
    open: Mapped[object | None] = mapped_column(Numeric(24, 8))
    high: Mapped[object | None] = mapped_column(Numeric(24, 8))
    low: Mapped[object | None] = mapped_column(Numeric(24, 8))
    close: Mapped[object | None] = mapped_column(Numeric(24, 8))
    source_code: Mapped[str] = mapped_column(String(48))
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data_status: Mapped[DataStatus] = mapped_column(Enum(DataStatus, name="data_status"))
    source_revision: Mapped[str | None] = mapped_column(String(64))
    ingestion_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("ingestion_runs.id"))
