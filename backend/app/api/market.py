import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis

from app.core.dependencies import market_spot_repository, redis_client
from app.core.errors import AppError
from app.domain.market_spot import InstitutionType, MarketSpotRepository
from app.domain.security import MarketCode
from app.services.market_spot import (
    CreditTradingService,
    InstitutionalService,
    MarketOverviewService,
)

router = APIRouter(prefix="/market", tags=["Market"])


@router.get("/overview", operation_id="getMarketOverview")
async def overview(
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    redis: Annotated[Redis, Depends(redis_client)],
):
    key = "market:overview:latest"
    try:
        if cached := await redis.get(key):
            return json.loads(cached)
    except Exception:
        pass
    result = await MarketOverviewService(repository).overview()
    try:
        await redis.set(key, json.dumps(result), ex=21600)
    except Exception:
        pass
    return result


@router.get("/indexes", operation_id="getMarketIndexes")
async def indexes(repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)]):
    rows = await repository.indexes(None, None, None, 2)
    return {"data": [MarketOverviewService._index(row) for row in rows]}


@router.get("/indexes/{index_code}", operation_id="getMarketIndex")
async def index(
    index_code: str, repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)]
):
    rows = await repository.indexes(index_code.upper(), None, None, 1)
    if not rows:
        raise AppError("INDEX_NOT_FOUND", "Market index was not found", 404)
    return {"data": MarketOverviewService._index(rows[-1])}


@router.get("/indexes/{index_code}/candles", operation_id="getMarketIndexCandles")
async def index_candles(
    index_code: str,
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    range: str = "30D",
):
    limits = {"5D": 5, "10D": 10, "30D": 30, "1Y": 250, "5Y": 1250}
    if range not in limits:
        raise AppError("INVALID_RANGE", "Unsupported index range", 422)
    rows = await repository.indexes(index_code.upper(), None, None, limits[range])
    if not rows:
        raise AppError("INDEX_NOT_FOUND", "Market index was not found", 404)
    return {"data": [MarketOverviewService._index(row) for row in rows], "range": range}


@router.get("/breadth", operation_id="getMarketBreadth")
async def breadth(
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    market: MarketCode | None = None,
    date_value: Annotated[date | None, Query(alias="date")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
):
    start, end = (date_value, date_value) if date_value else (from_date, to)
    rows = await repository.breadth(market, start, end)
    return {"data": [MarketOverviewService._breadth(row) for row in rows]}


@router.get("/institutional/spot", operation_id="getMarketInstitutionalSpot")
async def institutional(
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    market: MarketCode,
    window: int = 1,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    institution: InstitutionType | None = None,
):
    try:
        data = await InstitutionalService(repository).series(
            market, None, window, from_date, to, institution
        )
    except ValueError as error:
        raise AppError("INVALID_WINDOW", str(error), 422) from error
    return {"data": data}


@router.get("/credit", operation_id="getMarketCredit")
async def credit(
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    market: MarketCode,
    window: int = 60,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
):
    try:
        return {
            "data": await CreditTradingService(repository).series(
                market, None, window, from_date, to
            )
        }
    except ValueError as error:
        raise AppError("INVALID_WINDOW", str(error), 422) from error
