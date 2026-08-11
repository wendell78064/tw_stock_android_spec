from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import derivatives_repository, market_spot_repository
from app.core.errors import AppError
from app.domain.derivatives import (
    TAIWAN_VIX_POLICY,
    DerivativesRepository,
    RollMethod,
    VixSourceCapability,
)
from app.domain.market_spot import MarketSpotRepository
from app.services.derivatives import (
    ContinuousFuturesService,
    DerivativesRiskService,
    FuturesService,
    OptionMaxPainService,
    encode,
    metadata,
)

router = APIRouter(tags=["Futures"])


@router.get("/futures/products", operation_id="getFuturesProducts")
async def products(repository: Annotated[DerivativesRepository, Depends(derivatives_repository)]):
    return {"data": [FuturesService._product(row) for row in await repository.products()]}


@router.get("/futures/products/{product_code}/overview", operation_id="getFuturesOverview")
async def overview(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    market_repository: Annotated[MarketSpotRepository, Depends(market_spot_repository)],
):
    result = await FuturesService(repository, market_repository).product_overview(
        product_code.upper()
    )
    if result is None:
        raise AppError("FUTURES_PRODUCT_NOT_FOUND", "Futures product was not found", 404)
    return {"data": result}


@router.get("/futures/products/{product_code}/contracts", operation_id="getFuturesContracts")
async def contracts(
    product_code: str, repository: Annotated[DerivativesRepository, Depends(derivatives_repository)]
):
    rows = await repository.contracts(product_code.upper())
    return {
        "data": [
            {
                name: encode(getattr(row, name))
                for name in (
                    "product_code",
                    "contract_code",
                    "contract_month",
                    "expiry_date",
                    "last_trade_date",
                    "status",
                    "is_active",
                )
            }
            for row in rows
        ]
    }


@router.get("/futures/contracts/{contract_code}/candles", operation_id="getFuturesContractCandles")
async def candles(
    contract_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    range: str = "30D",
):
    limits = {"5D": 5, "10D": 10, "30D": 30, "1Y": 250, "5Y": 1250}
    if range not in limits:
        raise AppError("INVALID_RANGE", "Unsupported futures range", 422)
    product = "".join(x for x in contract_code.upper() if x.isalpha())
    rows = await repository.daily(product, contract_code.upper(), limits[range])
    if not rows:
        raise AppError("FUTURES_CONTRACT_NOT_FOUND", "Futures contract was not found", 404)
    return {"data": [FuturesService._daily(row) for row in rows], "range": range}


@router.get(
    "/futures/products/{product_code}/continuous-candles",
    operation_id="getContinuousFuturesCandles",
)
async def continuous(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    range: str = "1Y",
    roll_method: RollMethod = RollMethod.OPEN_INTEREST,
):
    limits = {"5D": 10, "10D": 20, "30D": 60, "1Y": 500, "5Y": 2500}
    if range not in limits:
        raise AppError("INVALID_RANGE", "Unsupported futures range", 422)
    rows = await repository.daily(product_code.upper(), None, limits[range])
    return {
        "data": ContinuousFuturesService().build(rows, roll_method),
        "range": range,
        "roll_method": roll_method.value,
        "adjustment_method": "NONE",
    }


@router.get("/futures/products/{product_code}/open-interest", operation_id="getFuturesOpenInterest")
async def open_interest(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    window: int = 60,
):
    if window not in (1, 5, 10, 20, 60):
        raise AppError("INVALID_WINDOW", "Unsupported trading window", 422)
    rows = await repository.daily(product_code.upper(), None, window * 2)
    return {
        "data": [
            {
                "trade_date": r.trade_date.isoformat(),
                "contract_code": r.contract_code,
                "open_interest": r.open_interest,
                **metadata(r),
            }
            for r in rows
        ]
    }


@router.get(
    "/futures/products/{product_code}/institutional-positions",
    operation_id="getFuturesInstitutionalPositions",
)
async def positions(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    window: int = 20,
):
    try:
        data = await FuturesService(repository).positions(product_code.upper(), window)
    except ValueError as error:
        raise AppError("INVALID_WINDOW", str(error), 422) from error
    return {"data": data}


@router.get(
    "/futures/products/{product_code}/trader-concentration", operation_id="getTraderConcentration"
)
async def concentration(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    window: int = 20,
):
    rows = await repository.concentrations(product_code.upper(), window)
    return {
        "data": [
            {
                name: encode(getattr(row, name))
                for name in (
                    "product_code",
                    "trade_date",
                    "contract_scope",
                    "side",
                    "top_n",
                    "open_interest",
                    "market_open_interest",
                    "concentration_ratio",
                    "specific_institution_oi",
                )
            }
            | metadata(row)
            for row in rows
        ]
    }


@router.get("/options/products/{product_code}/put-call-ratio", operation_id="getPutCallRatio")
async def put_call(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    window: int = 20,
):
    limits = {1: 1, 5: 5, 10: 10, 20: 20, 60: 60, 250: 250}
    if window not in limits:
        raise AppError("INVALID_WINDOW", "Unsupported trading window", 422)
    rows = await repository.put_call(product_code.upper(), limits[window])
    return {
        "data": [
            {
                name: encode(getattr(row, name))
                for name in (
                    "product_code",
                    "trade_date",
                    "put_volume",
                    "call_volume",
                    "volume_put_call_ratio",
                    "put_open_interest",
                    "call_open_interest",
                    "oi_put_call_ratio",
                )
            }
            | metadata(row)
            for row in rows
        ]
    }


@router.get(
    "/options/products/{product_code}/open-interest-by-strike",
    operation_id="getOptionStrikeOpenInterest",
)
async def strike_oi(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    expiry: str | None = None,
    date_value: Annotated[date | None, Query(alias="date")] = None,
):
    rows = await repository.strike_oi(product_code.upper(), expiry, date_value)
    return {
        "data": [
            {
                name: encode(getattr(row, name))
                for name in (
                    "product_code",
                    "expiry",
                    "trade_date",
                    "option_type",
                    "strike",
                    "open_interest",
                    "volume",
                    "settlement_price",
                )
            }
            | metadata(row)
            for row in rows
        ]
    }


@router.get("/options/products/{product_code}/max-pain", operation_id="getOptionMaxPain")
async def max_pain(
    product_code: str,
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    expiry: str | None = None,
    date_value: Annotated[date | None, Query(alias="date")] = None,
):
    rows = await repository.strike_oi(product_code.upper(), expiry, date_value)
    return {"data": OptionMaxPainService().calculate(rows)}


@router.get("/market/volatility", operation_id="getMarketVolatility")
async def volatility(
    repository: Annotated[DerivativesRepository, Depends(derivatives_repository)],
    range: str = "30D",
):
    limits = {"1D": 1, "5D": 5, "10D": 10, "30D": 30, "1Y": 250, "5Y": 1250}
    if range not in limits:
        raise AppError("INVALID_RANGE", "Unsupported volatility range", 422)
    data = await DerivativesRiskService(repository).volatility(limits[range])
    policy = TAIWAN_VIX_POLICY
    return {
        "data": data,
        "range": range,
        "meta": {
            "data_status": "FINAL" if data else "UNAVAILABLE",
            "source_type": policy.source_type.value,
            "source_capability": VixSourceCapability.OFFICIAL_DOWNLOAD.value,
            "license_status": policy.license_status.value,
            "automation_allowed": policy.automation_allowed,
            "storage_allowed": policy.storage_allowed,
            "redistribution_allowed": policy.redistribution_allowed,
        },
    }
