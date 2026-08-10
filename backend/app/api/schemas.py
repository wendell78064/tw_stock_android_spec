from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.market_data import DataStatus
from app.domain.pricing import Candle, PriceBasis, TechnicalSnapshot
from app.domain.security import MarketCode, Security, SecurityStatus, SecurityType


class MetaResponse(BaseModel):
    as_of: datetime
    received_at: datetime
    data_status: DataStatus
    source: str


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
                exclude={"status", "listing_date", "source"}
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
        parameters = {
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


class TechnicalSeriesEnvelope(BaseModel):
    data: list[TechnicalPointResponse]
    meta: MetaResponse
