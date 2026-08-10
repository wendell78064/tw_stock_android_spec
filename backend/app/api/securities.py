from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.schemas import (
    CandleResponse,
    CandleSeriesEnvelope,
    MetaResponse,
    SecurityEnvelope,
    SecurityResponse,
    SecuritySearchEnvelope,
    SecuritySearchItem,
    TechnicalPointResponse,
    TechnicalSeriesEnvelope,
    meta_for,
)
from app.core.dependencies import price_repository, security_repository
from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.pricing import CandleInterval, ChartRange, PriceBasis, PriceRepository, SecurityKey
from app.domain.security import MarketCode, SecurityRepository, SecurityType
from app.services.candle_aggregation import CandleAggregationService, range_start

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


async def _require_security(repository: SecurityRepository, code: str, market: MarketCode):
    securities = await repository.find_by_code(code, market)
    if not securities:
        raise AppError(
            "SECURITY_NOT_FOUND", "找不到指定股票", 404, {"code": code, "market": market.value}
        )
    return securities[0]


@router.get(
    "/{code}/candles", response_model=CandleSeriesEnvelope, operation_id="getSecurityCandles"
)
async def get_candles(
    code: str,
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
    market: MarketCode,
    range: ChartRange = ChartRange.ONE_YEAR,
    interval: CandleInterval = CandleInterval.DAY,
    adjustment: PriceBasis = PriceBasis.ADJUSTED,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> CandleSeriesEnvelope:
    await _require_security(securities, code, market)
    end = to or date.today()
    records = await prices.list_prices(
        SecurityKey(market, code), from_date or range_start(end, range.value), end
    )
    if not records:
        now = datetime.now(UTC)
        return CandleSeriesEnvelope(
            data=[],
            meta=MetaResponse(
                as_of=now,
                received_at=now,
                data_status=DataStatus.UNAVAILABLE,
                source="DAILY_PRICES",
            ),
            interval=interval.value,
            adjustment=adjustment,
            display_note="沒有可用日 K 資料",
        )
    candles = CandleAggregationService().aggregate(records, interval, adjustment)
    day_counts = {
        ChartRange.ONE_DAY: 1,
        ChartRange.FIVE_DAYS: 5,
        ChartRange.TEN_DAYS: 10,
        ChartRange.THIRTY_DAYS: 30,
    }
    if range in day_counts and from_date is None:
        candles = candles[-day_counts[range] :]
    status = (
        DataStatus.UNAVAILABLE
        if not candles and adjustment is PriceBasis.ADJUSTED
        else (
            DataStatus.PARTIAL
            if len({item.data_status for item in records}) > 1
            else records[-1].data_status
        )
    )
    return CandleSeriesEnvelope(
        data=[CandleResponse.from_domain(item) for item in candles],
        meta=MetaResponse(
            as_of=max(item.as_of for item in records),
            received_at=max(item.received_at for item in records),
            data_status=status,
            source=",".join(sorted({item.source_code for item in records})),
        ),
        interval=interval.value,
        adjustment=adjustment,
        display_note="最近交易日日 K；不代表盤中分時" if range is ChartRange.ONE_DAY else None,
    )


@router.get(
    "/{code}/technicals",
    response_model=TechnicalSeriesEnvelope,
    operation_id="getSecurityTechnicals",
)
async def get_technicals(
    code: str,
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
    market: MarketCode,
    price_basis: PriceBasis = PriceBasis.ADJUSTED,
    date_value: Annotated[date | None, Query(alias="date")] = None,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    indicators: str | None = None,
) -> TechnicalSeriesEnvelope:
    await _require_security(securities, code, market)
    start, end = (date_value, date_value) if date_value else (from_date, to)
    snapshots = await prices.list_technicals(SecurityKey(market, code), price_basis, start, end)
    selected = {item.strip().upper() for item in indicators.split(",")} if indicators else None
    now = datetime.now(UTC)
    meta = MetaResponse(
        as_of=max((item.as_of for item in snapshots), default=now),
        received_at=max((item.received_at for item in snapshots), default=now),
        data_status=(snapshots[-1].data_status if snapshots else DataStatus.UNAVAILABLE),
        source="TECHNICAL_INDICATORS",
    )
    return TechnicalSeriesEnvelope(
        data=[TechnicalPointResponse.from_domain(item, selected) for item in snapshots], meta=meta
    )
