from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
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
