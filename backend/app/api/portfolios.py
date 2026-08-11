from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.core.dependencies import (
    portfolio_repository,
    price_repository,
    security_repository,
)
from app.domain.portfolio import LotType, PortfolioRepository, TransactionSide
from app.domain.pricing import PriceRepository
from app.domain.security import MarketCode, SecurityRepository
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/portfolios", tags=["Portfolios"])


class PortfolioInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_currency: str = Field(default="TWD", pattern="^[A-Z]{3}$")


class TransactionInput(BaseModel):
    security_code: str = Field(min_length=2, max_length=16)
    market: MarketCode | None = None
    side: TransactionSide
    executed_at: datetime
    quantity_shares: int = Field(gt=0)
    price: Decimal = Field(gt=0)
    fee: Decimal = Field(ge=0)
    lot_type: LotType


def decimal(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def portfolio(row) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "base_currency": row.base_currency,
        "is_default": row.is_default,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def transaction(row) -> dict:
    return {
        "id": str(row.id),
        "portfolio_id": str(row.portfolio_id),
        "security_code": row.security.code,
        "security_name": row.security_name,
        "market": row.security.market.value,
        "side": row.side.value,
        "executed_at": row.executed_at.isoformat(),
        "quantity_shares": row.quantity_shares,
        "price": decimal(row.price),
        "fee": decimal(row.fee),
        "lot_type": row.lot_type.value,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
        "tax_handling": "NOT_INCLUDED",
    }


def service(portfolios, securities, prices) -> PortfolioService:
    return PortfolioService(portfolios, securities, prices)


@router.get("", operation_id="listPortfolios")
async def list_portfolios(
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
):
    return {"data": [portfolio(row) for row in await repository.list_portfolios()]}


@router.post("", status_code=201, operation_id="createPortfolio")
async def create_portfolio(
    payload: PortfolioInput,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
):
    return {
        "data": portfolio(await repository.create_portfolio(payload.name, payload.base_currency))
    }


@router.get("/{portfolio_id}", operation_id="getPortfolio")
async def get_portfolio(
    portfolio_id: UUID,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    return {
        "data": portfolio(
            await service(repository, securities, prices).require_portfolio(portfolio_id)
        )
    }


@router.get("/{portfolio_id}/transactions", operation_id="listPortfolioTransactions")
async def list_transactions(
    portfolio_id: UUID,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    await service(repository, securities, prices).require_portfolio(portfolio_id)
    return {"data": [transaction(row) for row in await repository.list_transactions(portfolio_id)]}


@router.post(
    "/{portfolio_id}/transactions", status_code=201, operation_id="createPortfolioTransaction"
)
async def create_transaction(
    portfolio_id: UUID,
    payload: TransactionInput,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    row = await service(repository, securities, prices).create_transaction(
        portfolio_id,
        payload.security_code,
        payload.market,
        payload.side,
        payload.executed_at,
        payload.quantity_shares,
        payload.price,
        payload.fee,
        payload.lot_type,
    )
    return {"data": transaction(row)}


@router.delete(
    "/{portfolio_id}/transactions/{transaction_id}",
    status_code=204,
    operation_id="deletePortfolioTransaction",
)
async def delete_transaction(
    portfolio_id: UUID,
    transaction_id: UUID,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    await service(repository, securities, prices).delete_transaction(portfolio_id, transaction_id)
    return Response(status_code=204)


@router.get("/{portfolio_id}/positions", operation_id="getPortfolioPositions")
async def positions(
    portfolio_id: UUID,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    rows = await service(repository, securities, prices).holdings(portfolio_id)
    return {
        "data": [
            {
                "security_code": row.position.security.code,
                "security_name": row.position.security_name,
                "market": row.position.security.market.value,
                "quantity_shares": row.position.quantity_shares,
                "average_cost": decimal(row.position.average_cost),
                "cost_basis": decimal(row.position.cost_basis),
                "realized_pnl": decimal(row.position.realized_pnl),
                "latest_price": decimal(row.latest_price),
                "price_as_of": row.price_as_of.isoformat() if row.price_as_of else None,
                "price_data_status": row.price_data_status.value,
                "market_value": decimal(row.market_value),
                "unrealized_pnl": decimal(row.unrealized_pnl),
                "unrealized_return_percent": decimal(row.unrealized_return_percent),
                "allocation_percent": decimal(row.allocation_percent),
            }
            for row in rows
        ]
    }


@router.get("/{portfolio_id}/summary", operation_id="getPortfolioSummary")
async def summary(
    portfolio_id: UUID,
    repository: Annotated[PortfolioRepository, Depends(portfolio_repository)],
    securities: Annotated[SecurityRepository, Depends(security_repository)],
    prices: Annotated[PriceRepository, Depends(price_repository)],
):
    result = await service(repository, securities, prices).summary(portfolio_id)
    return {
        "data": {
            key: decimal(value)
            if isinstance(value, Decimal)
            else value.value
            if hasattr(value, "value")
            else value
            for key, value in result.items()
        }
    }
