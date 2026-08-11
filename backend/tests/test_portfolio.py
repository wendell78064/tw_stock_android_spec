from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import portfolio_repository, price_repository, security_repository
from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.portfolio import (
    LotType,
    Portfolio,
    PortfolioTransaction,
    TransactionSide,
)
from app.domain.pricing import DailyPriceRecord, SecurityKey
from app.domain.security import MarketCode, Security, SecurityStatus, SecurityType
from app.main import app
from app.services.portfolio import PortfolioAccountingService, PortfolioService

NOW = datetime(2026, 8, 11, tzinfo=UTC)
PORTFOLIO_ID = UUID("00000000-0000-0000-0000-000000000001")
SECURITY_ID = UUID("00000000-0000-0000-0000-000000000002")
KEY = SecurityKey(MarketCode.TWSE, "2330")


def tx(
    side: TransactionSide,
    quantity: int,
    price: str,
    fee: str = "0",
    *,
    sequence: int = 1,
    security_id: UUID = SECURITY_ID,
    key: SecurityKey = KEY,
) -> PortfolioTransaction:
    timestamp = NOW + timedelta(seconds=sequence)
    return PortfolioTransaction(
        UUID(int=sequence),
        PORTFOLIO_ID,
        security_id,
        key,
        key.code,
        side,
        timestamp,
        quantity,
        Decimal(price),
        Decimal(fee),
        LotType.ROUND_LOT if quantity % 1000 == 0 else LotType.ODD_LOT,
        timestamp,
        timestamp,
    )


def test_first_and_multiple_buy_average_cost_and_fee() -> None:
    positions = PortfolioAccountingService().replay(
        [
            tx(TransactionSide.BUY, 1000, "10", "20", sequence=1),
            tx(TransactionSide.BUY, 500, "16", "10", sequence=2),
        ]
    )
    assert positions[0].quantity_shares == 1500
    assert positions[0].cost_basis == Decimal("18030")
    assert positions[0].average_cost == Decimal("12.02")
    assert positions[0].realized_pnl == 0


def test_partial_sell_fee_and_remaining_average_cost() -> None:
    position = PortfolioAccountingService().replay(
        [
            tx(TransactionSide.BUY, 1000, "10", sequence=1),
            tx(TransactionSide.SELL, 400, "15", "20", sequence=2),
        ]
    )[0]
    assert position.quantity_shares == 600
    assert position.average_cost == Decimal("10")
    assert position.cost_basis == Decimal("6000")
    assert position.realized_pnl == Decimal("1980")


def test_full_sell_resets_basis_and_average_cost() -> None:
    position = PortfolioAccountingService().replay(
        [
            tx(TransactionSide.BUY, 1000, "10", sequence=1),
            tx(TransactionSide.SELL, 1000, "11", sequence=2),
        ]
    )[0]
    assert (position.quantity_shares, position.cost_basis, position.average_cost) == (0, 0, None)
    assert position.realized_pnl == Decimal("1000")


def test_oversell_is_rejected_without_negative_position() -> None:
    with pytest.raises(AppError) as error:
        PortfolioAccountingService().replay(
            [
                tx(TransactionSide.BUY, 100, "10", sequence=1),
                tx(TransactionSide.SELL, 101, "10", sequence=2),
            ]
        )
    assert error.value.code == "PORTFOLIO_INSUFFICIENT_POSITION"


def test_multiple_securities_and_same_timestamp_are_deterministic() -> None:
    other_id = UUID("00000000-0000-0000-0000-000000000003")
    other = SecurityKey(MarketCode.TPEX, "6488")
    rows = [
        tx(TransactionSide.BUY, 100, "10", sequence=2),
        replace(tx(TransactionSide.BUY, 100, "20", sequence=1), executed_at=NOW),
        tx(TransactionSide.BUY, 50, "30", sequence=3, security_id=other_id, key=other),
    ]
    first = PortfolioAccountingService().replay(rows)
    second = PortfolioAccountingService().replay(list(reversed(rows)))
    assert first == second
    assert len(first) == 2


class MemoryPortfolioRepository:
    def __init__(self, transactions=None):
        self.portfolio = Portfolio(PORTFOLIO_ID, "Default", "TWD", True, NOW, NOW)
        self.transactions = list(transactions or [])

    async def list_portfolios(self):
        return [self.portfolio]

    async def create_portfolio(self, name, base_currency):
        self.portfolio = replace(
            self.portfolio, id=uuid4(), name=name, base_currency=base_currency, is_default=False
        )
        return self.portfolio

    async def get_portfolio(self, portfolio_id):
        return self.portfolio if portfolio_id == PORTFOLIO_ID else None

    async def list_transactions(self, portfolio_id):
        return list(self.transactions) if portfolio_id == PORTFOLIO_ID else []

    async def add_transaction(
        self, portfolio_id, security_id, side, executed_at, quantity_shares, price, fee, lot_type
    ):
        row = tx(side, quantity_shares, str(price), str(fee), sequence=len(self.transactions) + 10)
        row = replace(row, executed_at=executed_at, lot_type=lot_type, security_id=security_id)
        self.transactions.append(row)
        return row

    async def delete_transaction(self, portfolio_id, transaction_id):
        before = len(self.transactions)
        self.transactions = [item for item in self.transactions if item.id != transaction_id]
        return len(self.transactions) != before


class MemorySecurityRepository:
    def __init__(self, duplicates=False):
        self.security = Security(
            SECURITY_ID,
            MarketCode.TWSE,
            "2330",
            "台積電",
            SecurityType.COMMON_STOCK,
            SecurityStatus.ACTIVE,
            True,
            None,
            None,
            "FIXTURE",
            NOW,
            NOW,
            DataStatus.FINAL,
        )
        self.duplicates = duplicates

    async def find_by_code(self, code, market):
        if code == "BAD":
            return []
        return (
            [self.security, replace(self.security, id=uuid4(), market=MarketCode.TPEX)]
            if self.duplicates and market is None
            else [self.security]
        )


class MemoryPriceRepository:
    def __init__(self, close: Decimal | None = Decimal("15"), status=DataStatus.FINAL):
        self.close, self.status = close, status

    async def list_prices(self, security, start, end):
        if self.close is None:
            return []
        return [
            DailyPriceRecord(
                security,
                date(2026, 8, 10),
                self.close,
                self.close,
                self.close,
                self.close,
                None,
                None,
                None,
                None,
                1,
                self.close,
                "FIXTURE",
                NOW,
                NOW,
                self.status,
            )
        ]


@pytest.mark.asyncio
async def test_latest_close_valuation_summary_and_allocation() -> None:
    repository = MemoryPortfolioRepository([tx(TransactionSide.BUY, 1000, "10", sequence=1)])
    service = PortfolioService(repository, MemorySecurityRepository(), MemoryPriceRepository())
    holding = (await service.holdings(PORTFOLIO_ID))[0]
    summary = await service.summary(PORTFOLIO_ID)
    assert holding.market_value == Decimal("15000")
    assert holding.unrealized_pnl == Decimal("5000")
    assert holding.allocation_percent == Decimal("100")
    assert summary["total_return_percent"] == Decimal("50.0")


@pytest.mark.asyncio
async def test_missing_and_stale_prices_are_not_zero_filled() -> None:
    repository = MemoryPortfolioRepository([tx(TransactionSide.BUY, 1000, "10")])
    missing = PortfolioService(repository, MemorySecurityRepository(), MemoryPriceRepository(None))
    holding = (await missing.holdings(PORTFOLIO_ID))[0]
    assert holding.latest_price is None and holding.market_value is None
    assert (await missing.summary(PORTFOLIO_ID))["data_status"] is DataStatus.PARTIAL
    stale = PortfolioService(
        repository, MemorySecurityRepository(), MemoryPriceRepository(status=DataStatus.STALE)
    )
    assert (await stale.summary(PORTFOLIO_ID))["data_status"] is DataStatus.STALE


@pytest.mark.asyncio
async def test_unknown_ambiguous_security_and_invalid_values() -> None:
    repository = MemoryPortfolioRepository()
    service = PortfolioService(repository, MemorySecurityRepository(), MemoryPriceRepository())
    with pytest.raises(AppError, match="找不到"):
        await service.create_transaction(
            PORTFOLIO_ID,
            "BAD",
            None,
            TransactionSide.BUY,
            NOW,
            1,
            Decimal("1"),
            Decimal("0"),
            LotType.ODD_LOT,
        )
    ambiguous = PortfolioService(
        repository, MemorySecurityRepository(True), MemoryPriceRepository()
    )
    with pytest.raises(AppError) as error:
        await ambiguous.create_transaction(
            PORTFOLIO_ID,
            "2330",
            None,
            TransactionSide.BUY,
            NOW,
            1,
            Decimal("1"),
            Decimal("0"),
            LotType.ODD_LOT,
        )
    assert error.value.code == "AMBIGUOUS_SECURITY"


@pytest.mark.asyncio
async def test_delete_replays_history_and_empty_portfolio() -> None:
    buy = tx(TransactionSide.BUY, 1000, "10", sequence=1)
    sell = tx(TransactionSide.SELL, 400, "15", sequence=2)
    repository = MemoryPortfolioRepository([buy, sell])
    service = PortfolioService(repository, MemorySecurityRepository(), MemoryPriceRepository())
    await service.delete_transaction(PORTFOLIO_ID, sell.id)
    assert (await service.holdings(PORTFOLIO_ID))[0].position.quantity_shares == 1000
    empty = PortfolioService(
        MemoryPortfolioRepository(), MemorySecurityRepository(), MemoryPriceRepository()
    )
    summary = await empty.summary(PORTFOLIO_ID)
    assert summary["holding_count"] == 0 and summary["total_cost_basis"] == 0


def test_replay_1000_transactions_is_single_pass_smoke() -> None:
    rows = [tx(TransactionSide.BUY, 1, "10", sequence=index + 1) for index in range(1000)]
    position = PortfolioAccountingService().replay(rows)[0]
    assert position.quantity_shares == 1000


def test_portfolio_api_contract_create_value_delete_and_errors() -> None:
    portfolios = MemoryPortfolioRepository()
    securities = MemorySecurityRepository()
    prices = MemoryPriceRepository()
    app.dependency_overrides[portfolio_repository] = lambda: portfolios
    app.dependency_overrides[security_repository] = lambda: securities
    app.dependency_overrides[price_repository] = lambda: prices
    try:
        with TestClient(app) as client:
            listed = client.get("/v1/portfolios")
            assert listed.status_code == 200 and listed.json()["data"][0]["is_default"]
            created = client.post(
                f"/v1/portfolios/{PORTFOLIO_ID}/transactions",
                json={
                    "security_code": "2330",
                    "market": "TWSE",
                    "side": "BUY",
                    "executed_at": "2026-08-11T09:00:00+08:00",
                    "quantity_shares": 1000,
                    "price": "10.25",
                    "fee": "20",
                    "lot_type": "ROUND_LOT",
                },
            )
            assert created.status_code == 201
            assert created.json()["data"]["price"] == "10.25"
            summary_response = client.get(f"/v1/portfolios/{PORTFOLIO_ID}/summary")
            assert summary_response.status_code == 200
            assert summary_response.json()["data"]["tax_handling"] == "NOT_INCLUDED"
            transaction_id = created.json()["data"]["id"]
            assert (
                client.delete(
                    f"/v1/portfolios/{PORTFOLIO_ID}/transactions/{transaction_id}"
                ).status_code
                == 204
            )
            error = client.post(
                f"/v1/portfolios/{PORTFOLIO_ID}/transactions",
                json={
                    "security_code": "2330",
                    "market": "TWSE",
                    "side": "SELL",
                    "executed_at": "2026-08-11T09:00:00+08:00",
                    "quantity_shares": 1,
                    "price": "10",
                    "fee": "0",
                    "lot_type": "ODD_LOT",
                },
            )
            assert error.status_code == 422
            assert error.json()["error"]["code"] == "PORTFOLIO_INSUFFICIENT_POSITION"
    finally:
        app.dependency_overrides.clear()
