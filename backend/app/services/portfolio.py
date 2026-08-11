from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.portfolio import (
    LotType,
    PortfolioHolding,
    PortfolioPosition,
    PortfolioRepository,
    PortfolioTransaction,
    TransactionSide,
)
from app.domain.pricing import PriceRepository, SecurityKey
from app.domain.security import MarketCode, SecurityRepository

ZERO = Decimal("0")


class PortfolioAccountingService:
    """Single-pass moving-average accounting; transactions are the source of truth."""

    def replay(self, transactions: list[PortfolioTransaction]) -> list[PortfolioPosition]:
        states: dict[UUID, PortfolioPosition] = {}
        ordered = sorted(
            transactions, key=lambda item: (item.executed_at, item.created_at, item.id.hex)
        )
        for transaction in ordered:
            current = states.get(
                transaction.security_id,
                PortfolioPosition(
                    transaction.security_id,
                    transaction.security,
                    transaction.security_name,
                    0,
                    None,
                    ZERO,
                    ZERO,
                ),
            )
            if transaction.side is TransactionSide.BUY:
                quantity = current.quantity_shares + transaction.quantity_shares
                basis = (
                    current.cost_basis
                    + transaction.price * transaction.quantity_shares
                    + transaction.fee
                )
                states[transaction.security_id] = replace(
                    current,
                    quantity_shares=quantity,
                    cost_basis=basis,
                    average_cost=basis / quantity,
                )
                continue
            if transaction.quantity_shares > current.quantity_shares:
                raise AppError(
                    "PORTFOLIO_INSUFFICIENT_POSITION",
                    "賣出股數超過目前可用持股",
                    422,
                    {
                        "security_code": transaction.security.code,
                        "available_shares": current.quantity_shares,
                        "requested_shares": transaction.quantity_shares,
                    },
                )
            average = current.cost_basis / current.quantity_shares
            sold_basis = average * transaction.quantity_shares
            quantity = current.quantity_shares - transaction.quantity_shares
            basis = ZERO if quantity == 0 else current.cost_basis - sold_basis
            realized = (
                current.realized_pnl
                + transaction.price * transaction.quantity_shares
                - transaction.fee
                - sold_basis
            )
            states[transaction.security_id] = replace(
                current,
                quantity_shares=quantity,
                cost_basis=basis,
                average_cost=None if quantity == 0 else basis / quantity,
                realized_pnl=realized,
            )
        return sorted(states.values(), key=lambda item: (item.security.market, item.security.code))


class PortfolioService:
    def __init__(
        self,
        portfolios: PortfolioRepository,
        securities: SecurityRepository,
        prices: PriceRepository,
    ):
        self.portfolios = portfolios
        self.securities = securities
        self.prices = prices
        self.accounting = PortfolioAccountingService()

    async def require_portfolio(self, portfolio_id: UUID):
        portfolio = await self.portfolios.get_portfolio(portfolio_id)
        if portfolio is None:
            raise AppError("PORTFOLIO_NOT_FOUND", "找不到投資組合", 404)
        return portfolio

    async def create_transaction(
        self,
        portfolio_id: UUID,
        security_code: str,
        market: MarketCode | None,
        side: TransactionSide,
        executed_at: datetime,
        quantity_shares: int,
        price: Decimal,
        fee: Decimal,
        lot_type: LotType,
    ) -> PortfolioTransaction:
        await self.require_portfolio(portfolio_id)
        matches = await self.securities.find_by_code(security_code, market)
        if not matches:
            raise AppError("SECURITY_NOT_FOUND", "找不到指定股票", 404)
        if len(matches) > 1:
            raise AppError("AMBIGUOUS_SECURITY", "股票代號存在於多個市場，請指定 market", 409)
        if quantity_shares <= 0 or price <= ZERO or fee < ZERO:
            raise AppError("PORTFOLIO_INVALID_TRANSACTION", "交易數值不符合規則", 422)
        candidate = PortfolioTransaction(
            UUID(int=(1 << 128) - 1),
            portfolio_id,
            matches[0].id,
            SecurityKey(matches[0].market, matches[0].code),
            matches[0].name,
            side,
            executed_at,
            quantity_shares,
            price,
            fee,
            lot_type,
            datetime.max.replace(tzinfo=UTC),
            datetime.max.replace(tzinfo=UTC),
        )
        self.accounting.replay([*await self.portfolios.list_transactions(portfolio_id), candidate])
        return await self.portfolios.add_transaction(
            portfolio_id,
            matches[0].id,
            side,
            executed_at,
            quantity_shares,
            price,
            fee,
            lot_type,
        )

    async def delete_transaction(self, portfolio_id: UUID, transaction_id: UUID) -> None:
        await self.require_portfolio(portfolio_id)
        transactions = await self.portfolios.list_transactions(portfolio_id)
        remaining = [item for item in transactions if item.id != transaction_id]
        if len(remaining) == len(transactions):
            raise AppError("PORTFOLIO_TRANSACTION_NOT_FOUND", "找不到交易", 404)
        self.accounting.replay(remaining)
        await self.portfolios.delete_transaction(portfolio_id, transaction_id)

    async def holdings(self, portfolio_id: UUID) -> list[PortfolioHolding]:
        await self.require_portfolio(portfolio_id)
        positions = self.accounting.replay(await self.portfolios.list_transactions(portfolio_id))
        holdings = []
        for position in positions:
            if position.quantity_shares == 0:
                continue
            rows = await self.prices.list_prices(position.security, None, None)
            latest = next((item for item in reversed(rows) if item.close is not None), None)
            if latest is None:
                holdings.append(
                    PortfolioHolding(position, None, None, DataStatus.UNAVAILABLE, None, None, None)
                )
                continue
            value = latest.close * position.quantity_shares
            unrealized = value - position.cost_basis
            holdings.append(
                PortfolioHolding(
                    position,
                    latest.close,
                    latest.as_of,
                    latest.data_status,
                    value,
                    unrealized,
                    unrealized / position.cost_basis * 100 if position.cost_basis else None,
                )
            )
        total_value = sum(
            (item.market_value for item in holdings if item.market_value is not None), ZERO
        )
        return [
            replace(
                item,
                allocation_percent=(item.market_value / total_value * 100)
                if item.market_value is not None and total_value
                else None,
            )
            for item in holdings
        ]

    async def summary(self, portfolio_id: UUID) -> dict:
        await self.require_portfolio(portfolio_id)
        transactions = await self.portfolios.list_transactions(portfolio_id)
        positions = self.accounting.replay(transactions)
        holdings = await self.holdings(portfolio_id)
        cost = sum((item.position.cost_basis for item in holdings), ZERO)
        realized = sum((item.realized_pnl for item in positions), ZERO)
        complete = all(item.market_value is not None for item in holdings)
        market_value = (
            sum((item.market_value for item in holdings if item.market_value is not None), ZERO)
            if complete
            else None
        )
        unrealized = market_value - cost if market_value is not None else None
        dates = {item.price_as_of for item in holdings if item.price_as_of is not None}
        statuses = {item.price_data_status for item in holdings}
        status = DataStatus.FINAL
        if not complete or len(dates) > 1 or len(statuses) > 1:
            status = DataStatus.PARTIAL
        if any(item is DataStatus.STALE for item in statuses):
            status = DataStatus.STALE
        return {
            "total_market_value": market_value,
            "total_cost_basis": cost,
            "total_unrealized_pnl": unrealized,
            "total_realized_pnl": realized,
            "total_return_percent": unrealized / cost * 100
            if unrealized is not None and cost
            else None,
            "holding_count": len(holdings),
            "price_as_of": min(dates).isoformat() if dates else None,
            "data_status": status,
            "tax_handling": "NOT_INCLUDED",
        }
