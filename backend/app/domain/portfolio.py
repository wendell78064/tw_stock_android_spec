from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.pricing import SecurityKey


class TransactionSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class LotType(StrEnum):
    ROUND_LOT = "ROUND_LOT"
    ODD_LOT = "ODD_LOT"


@dataclass(frozen=True)
class Portfolio:
    id: UUID
    name: str
    base_currency: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PortfolioTransaction:
    id: UUID
    portfolio_id: UUID
    security_id: UUID
    security: SecurityKey
    security_name: str
    side: TransactionSide
    executed_at: datetime
    quantity_shares: int
    price: Decimal
    fee: Decimal
    lot_type: LotType
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class PortfolioPosition:
    security_id: UUID
    security: SecurityKey
    security_name: str
    quantity_shares: int
    average_cost: Decimal | None
    cost_basis: Decimal
    realized_pnl: Decimal


@dataclass(frozen=True)
class PortfolioHolding:
    position: PortfolioPosition
    latest_price: Decimal | None
    price_as_of: datetime | None
    price_data_status: DataStatus
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    unrealized_return_percent: Decimal | None
    allocation_percent: Decimal | None = None


class PortfolioRepository(Protocol):
    async def list_portfolios(self) -> list[Portfolio]: ...
    async def get_portfolio(self, portfolio_id: UUID) -> Portfolio | None: ...
    async def create_portfolio(self, name: str, base_currency: str) -> Portfolio: ...
    async def list_transactions(self, portfolio_id: UUID) -> list[PortfolioTransaction]: ...
    async def add_transaction(
        self,
        portfolio_id: UUID,
        security_id: UUID,
        side: TransactionSide,
        executed_at: datetime,
        quantity_shares: int,
        price: Decimal,
        fee: Decimal,
        lot_type: LotType,
    ) -> PortfolioTransaction: ...
    async def delete_transaction(self, portfolio_id: UUID, transaction_id: UUID) -> bool: ...
