from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.schemas import (
    AddThemeSecurityInput,
    CreateThemeInput,
    MemberSecurityResponse,
    MetaResponse,
    TaxonomyLeaderResponse,
    TaxonomyStrengthDetailEnvelope,
    TaxonomyStrengthDetailResponse,
    TaxonomyStrengthListEnvelope,
    TaxonomyStrengthResponse,
    ThemeEnvelope,
    ThemeListEnvelope,
    ThemeResponse,
    ThemeSecuritiesEnvelope,
    UpdateThemeInput,
)
from app.core.dependencies import industry_repository, industry_strength_repository, require_admin_key
from app.core.errors import AppError
from app.domain.industry import IndustryRepository
from app.domain.market_data import DataStatus
from app.repositories.sql_industry_strength import SqlIndustryStrengthRepository

router = APIRouter(prefix="/themes", tags=["Themes"])


@router.get("", response_model=ThemeListEnvelope, operation_id="listThemes")
async def list_themes(
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeListEnvelope:
    themes = await repository.list_themes()
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL if themes else DataStatus.UNAVAILABLE,
        source="SECURITY_MASTER",
    )
    return ThemeListEnvelope(
        data=[ThemeResponse.from_domain(t) for t in themes],
        meta=meta,
    )


@router.post(
    "",
    response_model=ThemeEnvelope,
    status_code=status.HTTP_201_CREATED,
    operation_id="createTheme",
    dependencies=[Depends(require_admin_key)],
)
async def create_theme(
    input_data: CreateThemeInput,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeEnvelope:
    try:
        theme = await repository.create_theme(
            code=input_data.code.strip(),
            name=input_data.name.strip(),
            description=input_data.description.strip() if input_data.description else None,
            classification_type=input_data.classification_type,
        )
    except Exception as error:
        raise AppError("CREATE_THEME_FAILED", f"無法建立題材: {error}", 400) from error
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        source="SECURITY_MASTER",
    )
    return ThemeEnvelope(
        data=ThemeResponse.from_domain(theme),
        meta=meta,
    )


@router.get("/{id}", response_model=ThemeEnvelope, operation_id="getTheme")
async def get_theme(
    id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeEnvelope:
    theme = await repository.get_theme(id)
    if theme is None:
        raise AppError("THEME_NOT_FOUND", "找不到指定題材", 404, {"id": str(id)})
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        source="SECURITY_MASTER",
    )
    return ThemeEnvelope(
        data=ThemeResponse.from_domain(theme),
        meta=meta,
    )


@router.put(
    "/{id}",
    response_model=ThemeEnvelope,
    operation_id="updateTheme",
    dependencies=[Depends(require_admin_key)],
)
async def update_theme(
    id: UUID,
    input_data: UpdateThemeInput,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeEnvelope:
    theme = await repository.update_theme(
        theme_id=id,
        name=input_data.name.strip() if input_data.name else None,
        description=input_data.description.strip() if input_data.description else None,
    )
    if theme is None:
        raise AppError("THEME_NOT_FOUND", "找不到指定題材", 404, {"id": str(id)})
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        source="SECURITY_MASTER",
    )
    return ThemeEnvelope(
        data=ThemeResponse.from_domain(theme),
        meta=meta,
    )


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="deleteTheme",
    dependencies=[Depends(require_admin_key)],
)
async def delete_theme(
    id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> None:
    success = await repository.delete_theme(id)
    if not success:
        raise AppError("THEME_NOT_FOUND", "找不到指定題材", 404, {"id": str(id)})
    return None


@router.get(
    "/{id}/securities",
    response_model=ThemeSecuritiesEnvelope,
    operation_id="getThemeSecurities",
)
async def get_theme_securities(
    id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeSecuritiesEnvelope:
    try:
        theme, members, as_of, status_val = await repository.list_theme_securities(id)
    except LookupError as error:
        raise AppError("THEME_NOT_FOUND", "找不到指定題材", 404, {"id": str(id)}) from error

    meta = MetaResponse(
        as_of=as_of,
        received_at=as_of,
        data_status=status_val,
        source="DAILY_PRICES",
    )
    return ThemeSecuritiesEnvelope(
        data=[MemberSecurityResponse.from_domain(mem) for mem in members],
        meta=meta,
    )


@router.post(
    "/{id}/securities",
    response_model=ThemeEnvelope,
    operation_id="addThemeSecurity",
    dependencies=[Depends(require_admin_key)],
)
async def add_theme_security(
    id: UUID,
    input_data: AddThemeSecurityInput,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> ThemeEnvelope:
    success = await repository.add_theme_security(id, input_data.security_id)
    if not success:
        raise AppError(
            "ADD_THEME_SECURITY_FAILED",
            "無法加入股票至題材，請確認題材與股票存在",
            400,
            {"theme_id": str(id), "security_id": str(input_data.security_id)},
        )
    theme = await repository.get_theme(id)
    if theme is None:
        raise AppError("THEME_NOT_FOUND", "找不到指定題材", 404, {"id": str(id)})
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        source="SECURITY_MASTER",
    )
    return ThemeEnvelope(
        data=ThemeResponse.from_domain(theme),
        meta=meta,
    )


@router.delete(
    "/{id}/securities/{security_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="removeThemeSecurity",
    dependencies=[Depends(require_admin_key)],
)
async def remove_theme_security(
    id: UUID,
    security_id: UUID,
    repository: Annotated[IndustryRepository, Depends(industry_repository)],
) -> None:
    success = await repository.remove_theme_security(id, security_id)
    if not success:
        raise AppError(
            "THEME_MEMBER_NOT_FOUND",
            "題材中無此股票關聯",
            404,
            {"theme_id": str(id), "security_id": str(security_id)},
        )
    return None


@router.get(
    "/strength",
    response_model=TaxonomyStrengthListEnvelope,
    operation_id="listThemeStrengths",
)
async def list_theme_strengths(
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    trade_date: date | None = None,
    sort: str = "strength",
) -> TaxonomyStrengthListEnvelope:
    strengths = await strength_repo.get_theme_strengths(window=window, trade_date=trade_date, sort_by=sort)
    now = datetime.now(UTC)
    as_of = strengths[0].as_of if strengths else now
    status_val = strengths[0].data_status if strengths else DataStatus.UNAVAILABLE
    meta = MetaResponse(
        as_of=as_of,
        received_at=now,
        data_status=status_val,
        source="STRENGTH_ENGINE",
    )
    return TaxonomyStrengthListEnvelope(
        data=[TaxonomyStrengthResponse.from_domain(s) for s in strengths],
        meta=meta,
    )


@router.get(
    "/{id}/strength",
    response_model=TaxonomyStrengthDetailEnvelope,
    operation_id="getThemeStrengthDetail",
)
async def get_theme_strength_detail(
    id: UUID,
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    trade_date: date | None = None,
) -> TaxonomyStrengthDetailEnvelope:
    detail = await strength_repo.get_taxonomy_strength_detail(taxonomy_id=id, is_industry=False, window=window, trade_date=trade_date)
    if detail is None:
        raise AppError("STRENGTH_NOT_FOUND", "找不到指定題材之強度快照", 404, {"id": str(id)})
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
            leaders=[TaxonomyLeaderResponse.from_domain(l) for l in detail.leaders],
            laggards=[TaxonomyLeaderResponse.from_domain(l) for l in detail.laggards],
        ),
        meta=meta,
    )


@router.get(
    "/{id}/strength/history",
    response_model=TaxonomyStrengthListEnvelope,
    operation_id="getThemeStrengthHistory",
)
async def get_theme_strength_history(
    id: UUID,
    strength_repo: Annotated[SqlIndustryStrengthRepository, Depends(industry_strength_repository)],
    window: int = 20,
    limit: int = 60,
) -> TaxonomyStrengthListEnvelope:
    history = await strength_repo.get_taxonomy_strength_history(taxonomy_id=id, is_industry=False, window=window, limit=limit)
    now = datetime.now(UTC)
    as_of = history[-1].as_of if history else now
    status_val = history[-1].data_status if history else DataStatus.UNAVAILABLE
    meta = MetaResponse(
        as_of=as_of,
        received_at=now,
        data_status=status_val,
        source="STRENGTH_ENGINE",
    )
    return TaxonomyStrengthListEnvelope(
        data=[TaxonomyStrengthResponse.from_domain(s) for s in history],
        meta=meta,
    )
