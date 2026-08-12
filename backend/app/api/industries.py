from datetime import UTC, date, datetime
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
    TaxonomyLeaderResponse,
    TaxonomyStrengthDetailEnvelope,
    TaxonomyStrengthDetailResponse,
    TaxonomyStrengthListEnvelope,
    TaxonomyStrengthResponse,
)
from app.core.dependencies import industry_repository, industry_strength_repository
from app.core.errors import AppError
from app.domain.industry import IndustryRepository
from app.domain.market_data import DataStatus
from app.repositories.sql_industry_strength import SqlIndustryStrengthRepository

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


@router.get(
    "/strength",
    response_model=TaxonomyStrengthListEnvelope,
    operation_id="listIndustryStrengths",
)
async def list_industry_strengths(
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    trade_date: date | None = None,
    sort: str = "strength",
) -> TaxonomyStrengthListEnvelope:
    strengths = await strength_repo.get_industry_strengths(
        window=window, trade_date=trade_date, sort_by=sort
    )
    now = datetime.now(UTC)
    as_of = strengths[0].as_of if strengths else now
    status = strengths[0].data_status if strengths else DataStatus.UNAVAILABLE
    meta = MetaResponse(
        as_of=as_of,
        received_at=now,
        data_status=status,
        source="STRENGTH_ENGINE",
    )
    return TaxonomyStrengthListEnvelope(
        data=[TaxonomyStrengthResponse.from_domain(s) for s in strengths],
        meta=meta,
    )


@router.get(
    "/{id}/strength",
    response_model=TaxonomyStrengthDetailEnvelope,
    operation_id="getIndustryStrengthDetail",
)
async def get_industry_strength_detail(
    id: UUID,
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    trade_date: date | None = None,
) -> TaxonomyStrengthDetailEnvelope:
    detail = await strength_repo.get_taxonomy_strength_detail(
        taxonomy_id=id, is_industry=True, window=window, trade_date=trade_date
    )
    if detail is None:
        raise AppError("STRENGTH_NOT_FOUND", "找不到指定產業之強度快照", 404, {"id": str(id)})
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=detail.snapshot.as_of,
        received_at=now,
        data_status=detail.snapshot.data_status,
        source="STRENGTH_ENGINE",
    )
    return TaxonomyStrengthDetailEnvelope(
        data=TaxonomyStrengthDetailResponse(
            snapshot=TaxonomyStrengthResponse.from_domain(detail.snapshot),
            leaders=[TaxonomyLeaderResponse.from_domain(ldr) for ldr in detail.leaders],
            laggards=[TaxonomyLeaderResponse.from_domain(ldr) for ldr in detail.laggards],
        ),
        meta=meta,
    )


@router.get(
    "/{id}/strength/history",
    response_model=TaxonomyStrengthListEnvelope,
    operation_id="getIndustryStrengthHistory",
)
async def get_industry_strength_history(
    id: UUID,
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    limit: int = 60,
) -> TaxonomyStrengthListEnvelope:
    history = await strength_repo.get_taxonomy_strength_history(
        taxonomy_id=id, is_industry=True, window=window, limit=limit
    )
    now = datetime.now(UTC)
    as_of = history[-1].as_of if history else now
    status = history[-1].data_status if history else DataStatus.UNAVAILABLE
    meta = MetaResponse(
        as_of=as_of,
        received_at=now,
        data_status=status,
        source="STRENGTH_ENGINE",
    )
    return TaxonomyStrengthListEnvelope(
        data=[TaxonomyStrengthResponse.from_domain(s) for s in history],
        meta=meta,
    )
