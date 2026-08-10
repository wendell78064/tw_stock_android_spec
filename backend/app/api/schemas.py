from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.market_data import DataStatus
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
