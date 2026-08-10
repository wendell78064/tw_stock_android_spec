from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.schemas import (
    SecurityEnvelope,
    SecurityResponse,
    SecuritySearchEnvelope,
    SecuritySearchItem,
    meta_for,
)
from app.core.dependencies import security_repository
from app.core.errors import AppError
from app.domain.security import MarketCode, SecurityRepository, SecurityType

router = APIRouter(prefix="/securities", tags=["Securities"])


@router.get("/search", response_model=SecuritySearchEnvelope, operation_id="searchSecurities")
async def search_securities(
    repository: Annotated[SecurityRepository, Depends(security_repository)],
    q: Annotated[str, Query(min_length=2)],
    market: MarketCode | None = None,
    type: SecurityType = SecurityType.COMMON_STOCK,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> SecuritySearchEnvelope:
    del type
    securities = await repository.search(q.strip(), market, limit)
    if not securities:
        from datetime import UTC, datetime

        from app.api.schemas import MetaResponse
        from app.domain.market_data import DataStatus

        now = datetime.now(UTC)
        return SecuritySearchEnvelope(
            data=[],
            meta=MetaResponse(
                as_of=now,
                received_at=now,
                data_status=DataStatus.UNAVAILABLE,
                source="SECURITY_MASTER",
            ),
        )
    return SecuritySearchEnvelope(
        data=[SecuritySearchItem.from_domain(item) for item in securities],
        meta=meta_for(securities),
    )


@router.get("/{code}", response_model=SecurityEnvelope, operation_id="getSecurity")
async def get_security(
    code: str,
    repository: Annotated[SecurityRepository, Depends(security_repository)],
    market: MarketCode | None = None,
) -> SecurityEnvelope:
    securities = await repository.find_by_code(code, market)
    if not securities:
        raise AppError(
            "SECURITY_NOT_FOUND", "找不到指定股票", 404, {"code": code, "market": market}
        )
    if len(securities) > 1:
        raise AppError(
            "AMBIGUOUS_SECURITY",
            "股票代號存在於多個市場，請指定 market",
            409,
            {"code": code, "markets": [item.market.value for item in securities]},
        )
    security = securities[0]
    return SecurityEnvelope(data=SecurityResponse.from_domain(security), meta=meta_for(securities))
