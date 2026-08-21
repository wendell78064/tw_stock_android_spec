from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AnalysisPromptEnvelope,
    AnalysisPromptResponse,
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
from app.core.dependencies import (
    current_user_optional,
    database_session,
    market_spot_repository,
    price_repository,
    security_repository,
)
from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.market_spot import InstitutionType, MarketSpotRepository
from app.domain.pricing import (
    CandleInterval,
    ChartRange,
    PriceBasis,
    PriceRepository,
    SecurityKey,
    TechnicalSnapshot,
)
from app.domain.security import MarketCode, SecurityRepository, SecurityType
from app.services.candle_aggregation import CandleAggregationService, range_start
from app.services.market_spot import CreditTradingService, InstitutionalService
from app.services.technical_indicators import (
    REQUEST_ALGORITHM_VERSION,
    TechnicalIndicatorService,
    TechnicalParameters,
)

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
    ma_periods: str | None = None,
    ema_periods: str | None = None,
    rsi_period: int | None = None,
    macd_fast: int | None = None,
    macd_slow: int | None = None,
    macd_signal: int | None = None,
    kd_period: int | None = None,
    kd_k_smoothing: int | None = None,
    kd_d_smoothing: int | None = None,
    bollinger_period: int | None = None,
    bollinger_stddev: Decimal | None = None,
    atr_period: int | None = None,
    williams_period: int | None = None,
) -> TechnicalSeriesEnvelope:
    await _require_security(securities, code, market)
    start, end = (date_value, date_value) if date_value else (from_date, to)
    custom_values = (
        ma_periods,
        ema_periods,
        rsi_period,
        macd_fast,
        macd_slow,
        macd_signal,
        kd_period,
        kd_k_smoothing,
        kd_d_smoothing,
        bollinger_period,
        bollinger_stddev,
        atr_period,
        williams_period,
    )
    if any(value is not None for value in custom_values):
        defaults = TechnicalParameters()
        try:

            def parse_periods(value: str | None, fallback: tuple[int, ...]) -> tuple[int, ...]:
                return (
                    tuple(int(item.strip()) for item in value.split(","))
                    if value is not None
                    else fallback
                )

            parameters = TechnicalParameters(
                ma_periods=parse_periods(ma_periods, defaults.ma_periods),
                ema_periods=parse_periods(ema_periods, defaults.ema_periods),
                rsi_period=rsi_period if rsi_period is not None else defaults.rsi_period,
                macd_fast=macd_fast if macd_fast is not None else defaults.macd_fast,
                macd_slow=macd_slow if macd_slow is not None else defaults.macd_slow,
                macd_signal=macd_signal if macd_signal is not None else defaults.macd_signal,
                kd_period=kd_period if kd_period is not None else defaults.kd_period,
                kd_k_smoothing=kd_k_smoothing
                if kd_k_smoothing is not None
                else defaults.kd_k_smoothing,
                kd_d_smoothing=kd_d_smoothing
                if kd_d_smoothing is not None
                else defaults.kd_d_smoothing,
                bollinger_period=bollinger_period
                if bollinger_period is not None
                else defaults.bollinger_period,
                bollinger_stddev=bollinger_stddev
                if bollinger_stddev is not None
                else defaults.bollinger_stddev,
                atr_period=atr_period if atr_period is not None else defaults.atr_period,
                williams_period=williams_period
                if williams_period is not None
                else defaults.williams_period,
            )
            parameters.validate()
        except (ValueError, ArithmeticError) as error:
            raise AppError("INVALID_TECHNICAL_PARAMETERS", str(error), 422) from error
        records = await prices.list_prices(SecurityKey(market, code), None, end)
        candles = CandleAggregationService().aggregate(records, CandleInterval.DAY, price_basis)
        series = TechnicalIndicatorService().calculate(candles, parameters)
        record_by_date = {item.trade_date: item for item in records}
        snapshots = [
            TechnicalSnapshot(
                SecurityKey(market, code),
                candle.trade_date,
                price_basis,
                values,
                REQUEST_ALGORITHM_VERSION,
                record_by_date[candle.trade_date].as_of,
                record_by_date[candle.trade_date].received_at,
                record_by_date[candle.trade_date].data_status,
                parameters.response_parameters(),
            )
            for candle, values in zip(candles, series.values, strict=True)
            if start is None or candle.trade_date >= start
        ]
    else:
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


@router.get("/{code}/institutional", operation_id="getSecurityInstitutionalSpot")
async def get_security_institutional(
    code: str,
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    market: MarketCode,
    window: int = 20,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    institution: InstitutionType | None = None,
):
    await _require_security(securities, code, market)
    try:
        data = await InstitutionalService(repository).series(
            market, SecurityKey(market, code), window, from_date, to, institution
        )
    except ValueError as error:
        raise AppError("INVALID_WINDOW", str(error), 422) from error
    return {"data": data}


@router.get("/{code}/credit", operation_id="getSecurityCredit")
async def get_security_credit(
    code: str,
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    market: MarketCode,
    window: int = 60,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
):
    await _require_security(securities, code, market)
    try:
        data = await CreditTradingService(repository).series(
            market, SecurityKey(market, code), window, from_date, to
        )
    except ValueError as error:
        raise AppError("INVALID_WINDOW", str(error), 422) from error
    return {"data": data}


@router.get(
    "/{code}/analysis-prompt",
    response_model=AnalysisPromptEnvelope,
    operation_id="getSecurityAnalysisPrompt",
)
async def get_security_analysis_prompt(
    code: str,
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
    market_spots: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
    session: Annotated[AsyncSession, Depends(database_session)],
    market: MarketCode,
    user: Annotated[Any, Depends(current_user_optional)] = None,
) -> AnalysisPromptEnvelope:
    from app.services.analysis_snapshot_service import AnalysisSnapshotService
    from app.services.individual_prompt_builder import IndividualAnalysisPromptBuilder

    sec = await _require_security(securities, code, market)
    user_id = user.id if user else None

    snapshot_service = AnalysisSnapshotService(session, securities, prices, market_spots)
    snapshot = await snapshot_service.build_snapshot(code, market, user_id=user_id)

    builder = IndividualAnalysisPromptBuilder()
    prompt_text = builder.build_prompt(snapshot)

    now = datetime.now(UTC)
    data_status = (
        DataStatus.COMPLETE
        if snapshot.data_quality.overall_status.value == "COMPLETE"
        else (
            DataStatus.PARTIAL
            if snapshot.data_quality.overall_status.value == "PARTIAL"
            else DataStatus.UNAVAILABLE
        )
    )

    response_data = AnalysisPromptResponse(
        security=SecurityResponse.from_domain(sec),
        as_of=snapshot.as_of,
        generated_at=snapshot.generated_at,
        prompt=prompt_text,
        character_count=len(prompt_text),
        data_status=data_status,
        portfolio_included=snapshot.portfolio_position is not None,
    )

    meta = MetaResponse(
        as_of=snapshot.as_of,
        received_at=now,
        data_status=data_status,
        source="TW_MARKET_LEDGER_PROMPT_BUILDER",
    )

    return AnalysisPromptEnvelope(data=response_data, meta=meta)

