from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.schemas import (
    IndustryEnvelope,
    IndustryListEnvelope,
    IndustryResponse,
    IndustrySecuritiesEnvelope,
    MemberSecurityResponse,
    MetaResponse,
)
from app.core.dependencies import industry_repository
from app.core.errors import AppError
from app.domain.industry import IndustryRepository
from app.domain.market_data import DataStatus

router = APIRouter(prefix="/industries", tags=["Industries"])


@router.get("", response_model=IndustryListEnvelope, operation_id="listIndustries")
async def list_industries(
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> IndustryListEnvelope:
    industries = await repository.list_industries()
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL if industries else DataStatus.UNAVAILABLE,
        source="SECURITY_MASTER",
    )
    return IndustryListEnvelope(
        data=[IndustryResponse.from_domain(ind) for ind in industries],
        meta=meta,
    )


@router.get("/{id}", response_model=IndustryEnvelope, operation_id="getIndustry")
async def get_industry(
    id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> IndustryEnvelope:
    industry = await repository.get_industry(id)
    if industry is None:
        raise AppError("INDUSTRY_NOT_FOUND", "找不到指定產業", 404, {"id": str(id)})
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        source="SECURITY_MASTER",
    )
    return IndustryEnvelope(
        data=IndustryResponse.from_domain(industry),
        meta=meta,
    )


@router.get(
    "/{id}/securities",
    response_model=IndustrySecuritiesEnvelope,
    operation_id="getIndustrySecurities",
)
async def get_industry_securities(
    id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> IndustrySecuritiesEnvelope:
    try:
        industry, members, as_of, status = await repository.list_industry_securities(id)
    except LookupError as error:
        raise AppError("INDUSTRY_NOT_FOUND", "找不到指定產業", 404, {"id": str(id)}) from error

    meta = MetaResponse(
        as_of=as_of,
        received_at=as_of,
        data_status=status,
        source="DAILY_PRICES",
    )
    return IndustrySecuritiesEnvelope(
        data=[MemberSecurityResponse.from_domain(mem) for mem in members],
        meta=meta,
    )
