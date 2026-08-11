from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.portfolio import (
    LotType,
    Portfolio,
    PortfolioTransaction,
    TransactionSide,
)
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode
from app.repositories.models import (
    MarketModel,
    PortfolioModel,
    PortfolioTransactionModel,
    SecurityModel,
)


class SqlPortfolioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_portfolios(self) -> list[Portfolio]:
        rows = (
            await self.session.scalars(
                select(PortfolioModel).order_by(
                    PortfolioModel.is_default.desc(), PortfolioModel.name
                )
            )
        ).all()
        return [self._portfolio(item) for item in rows]

    async def get_portfolio(self, portfolio_id: UUID) -> Portfolio | None:
        row = await self.session.get(PortfolioModel, portfolio_id)
        return self._portfolio(row) if row else None

    async def create_portfolio(self, name: str, base_currency: str) -> Portfolio:
        now = datetime.now(UTC)
        row = PortfolioModel(
            name=name, base_currency=base_currency, is_default=False, created_at=now, updated_at=now
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._portfolio(row)

    async def list_transactions(self, portfolio_id: UUID) -> list[PortfolioTransaction]:
        statement = (
            select(PortfolioTransactionModel, SecurityModel, MarketModel.code)
            .join(SecurityModel, SecurityModel.id == PortfolioTransactionModel.security_id)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(PortfolioTransactionModel.portfolio_id == portfolio_id)
            .order_by(
                PortfolioTransactionModel.executed_at,
                PortfolioTransactionModel.created_at,
                PortfolioTransactionModel.id,
            )
        )
        return [self._transaction(*row) for row in (await self.session.execute(statement)).all()]

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
    ) -> PortfolioTransaction:
        now = datetime.now(UTC)
        row = PortfolioTransactionModel(
            portfolio_id=portfolio_id,
            security_id=security_id,
            side=side.value,
            executed_at=executed_at,
            quantity_shares=quantity_shares,
            price=price,
            fee=fee,
            lot_type=lot_type.value,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.commit()
        result = await self.session.execute(
            select(PortfolioTransactionModel, SecurityModel, MarketModel.code)
            .join(SecurityModel, SecurityModel.id == PortfolioTransactionModel.security_id)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(PortfolioTransactionModel.id == row.id)
        )
        return self._transaction(*result.one())

    async def delete_transaction(self, portfolio_id: UUID, transaction_id: UUID) -> bool:
        result = await self.session.execute(
            delete(PortfolioTransactionModel).where(
                PortfolioTransactionModel.portfolio_id == portfolio_id,
                PortfolioTransactionModel.id == transaction_id,
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    @staticmethod
    def _portfolio(row: PortfolioModel) -> Portfolio:
        return Portfolio(
            row.id,
            row.name,
            row.base_currency,
            row.is_default,
            row.created_at,
            row.updated_at,
        )

    @staticmethod
    def _transaction(
        row: PortfolioTransactionModel, security: SecurityModel, market: str
    ) -> PortfolioTransaction:
        return PortfolioTransaction(
            row.id,
            row.portfolio_id,
            row.security_id,
            SecurityKey(MarketCode(market), security.code),
            security.name,
            TransactionSide(row.side),
            row.executed_at,
            row.quantity_shares,
            Decimal(row.price),
            Decimal(row.fee),
            LotType(row.lot_type),
            row.created_at,
            row.updated_at,
        )
