from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.market_spot_mapping import map_institution
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TWSE_LENDING_CAPABILITIES, TwseSecurityProvider
from app.core.dependencies import (
    derivatives_repository,
    market_spot_repository,
    security_repository,
)
from app.domain.market_spot import InstitutionType, SourceCapability
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode
from app.main import app
from app.services.market_spot import (
    CreditTradingService,
    InstitutionalService,
    MarketOverviewService,
)
from app.services.market_spot_ingestion import DATASETS, MarketSpotIngestionService, validate_record
from tests.fakes import FakeSession, InMemorySecurityRepository


class MemoryMarketSpotRepository:
    def __init__(self):
        self.data = {name: [] for name in DATASETS}

    async def synchronize(self, dataset, records, run_id: UUID):
        del run_id
        inserted = updated = 0
        for record in records:
            identity = self._id(record)
            existing = next(
                (item for item in self.data[dataset] if self._id(item) == identity), None
            )
            if existing is None:
                self.data[dataset].append(record)
                inserted += 1
            elif existing != record:
                self.data[dataset].remove(existing)
                self.data[dataset].append(record)
                updated += 1
        return inserted, updated

    @staticmethod
    def _id(row):
        return (
            getattr(row, "security", None),
            getattr(row, "market", None),
            getattr(row, "code", None),
            row.trade_date,
            getattr(row, "institution_type", None),
            getattr(row, "dealer_subtype", None),
        )

    async def indexes(self, code, start, end, limit=None):
        rows = [
            r
            for r in self.data["MARKET_INDEXES"]
            if (not code or r.code == code)
            and (not start or r.trade_date >= start)
            and (not end or r.trade_date <= end)
        ]
        rows.sort(key=lambda r: r.trade_date)
        return rows[-limit:] if limit else rows

    async def breadth(self, market, start, end):
        return [
            r
            for r in self.data["MARKET_BREADTH"]
            if (not market or r.market == market)
            and (not start or r.trade_date >= start)
            and (not end or r.trade_date <= end)
        ]

    async def institutional(self, market, security, start, end, institution=None):
        key = "SECURITY_INSTITUTIONAL" if security else "MARKET_INSTITUTIONAL"
        return [
            r
            for r in self.data[key]
            if r.market == market
            and r.security == security
            and (not start or r.trade_date >= start)
            and (not end or r.trade_date <= end)
            and (not institution or r.institution_type == institution)
        ]

    async def margins(self, market, security, start, end):
        key = "SECURITY_MARGIN" if security else "MARKET_MARGIN"
        return [r for r in self.data[key] if r.market == market and r.security == security]

    async def lending(self, market, security, start, end):
        key = "SECURITY_LENDING" if security else "MARKET_LENDING"
        return [r for r in self.data[key] if r.market == market and r.security == security]


class EmptyDerivativesRepository:
    async def products(self, product_code=None):
        return []

    async def contracts(self, product_code):
        return []

    async def daily(self, product_code, contract_code, limit):
        return []

    async def positions(self, product_code, limit):
        return []

    async def concentrations(self, product_code, limit):
        return []

    async def put_call(self, product_code, limit):
        return []

    async def strike_oi(self, product_code, expiry, trade_date):
        return []

    async def volatility(self, code, limit):
        return []


def test_twse_tpex_official_field_mapping() -> None:
    now = datetime(2026, 8, 7, tzinfo=UTC)
    target = now.date()
    twse = TwseSecurityProvider()
    tpex = TpexSecurityProvider()
    taiex = twse.map_index_row(
        {
            "開盤指數": "22,000.5",
            "最高指數": "22,100",
            "最低指數": "21,900",
            "收盤指數": "22,050",
            "漲跌點數": "50",
            "漲跌百分比": "0.23%",
            "成交金額": "320,000",
            "成交筆數": "1,000",
        },
        trade_date=target,
        received_at=now,
    )
    otc = tpex.map_index_row(
        {
            "Open": "250",
            "High": "252",
            "Low": "249",
            "Close": "251",
            "Change": "1",
            "ChangePercent": "0.4",
            "TransactionAmount": "1000",
            "TransactionCount": "20",
        },
        trade_date=target,
        received_at=now,
    )
    assert (taiex.code, taiex.close, otc.code, otc.close) == ("TAIEX", 22050, "OTC", 251)
    margin = twse.map_margin_row(
        {
            "股票代號": "1234",
            "融資買進": "1,000",
            "融資賣出": "900",
            "融資今日餘額": "5,000",
            "融券賣出": "100",
            "融券買進": "80",
            "融券今日餘額": "500",
            "券資比": "10.0",
        },
        trade_date=target,
        received_at=now,
    )
    lending = tpex.map_lending_row(
        {
            "SecuritiesCompanyCode": "5678",
            "LendingSale": "50",
            "LendingReturn": "20",
            "LendingBalance": "300",
            "LendingChange": "30",
        },
        trade_date=target,
        received_at=now,
    )
    assert margin.security.code == "1234" and margin.margin_balance == 5000
    institutional = map_institution(
        {"買進金額": "2,000", "賣出金額": "1,250"},
        market=MarketCode.TWSE,
        trade_date=target,
        received_at=now,
        source="TWSE_T86",
        institution=InstitutionType.FOREIGN,
        buy_key="買進金額",
        sell_key="賣出金額",
    )
    assert lending.security.code == "5678" and lending.lending_balance_change == 30
    assert institutional.net == 750 and institutional.metadata.source_code == "TWSE_T86"


def test_twse_lending_short_mapping_preserves_unsupported_nulls() -> None:
    row = TwseSecurityProvider().map_lending_row(
        {"股票代號": "2330", "借券賣出股數": "1,234"},
        trade_date=date(2026, 8, 7),
        received_at=datetime(2026, 8, 7, tzinfo=UTC),
    )
    assert row.lending_short_sell == 1234
    assert row.lending_return is None
    assert row.lending_balance is None
    assert row.lending_balance_change is None
    assert row.metadata.data_status.value == "PARTIAL"
    assert TWSE_LENDING_CAPABILITIES == {
        "borrowed_shares": SourceCapability.UNAVAILABLE,
        "returned_shares": SourceCapability.UNAVAILABLE,
        "borrowing_balance": SourceCapability.UNAVAILABLE,
        "lending_short_sell": SourceCapability.OFFICIAL_OPENAPI,
        "lending_short_balance": SourceCapability.UNAVAILABLE,
    }


@pytest.mark.asyncio
async def test_fake_provider_mapping_validation_and_ingestion_idempotency() -> None:
    provider = FakeMarketDataProvider()
    target = date(2026, 8, 7)
    indexes = await provider.get_market_indexes(target)
    assert {item.code for item in indexes} == {"TAIEX", "OTC"}
    assert all(validate_record(item) is None for item in indexes)
    institutions = await provider.get_security_institutional_spot(target)
    foreign = next(
        item
        for item in institutions
        if item.security.code == "1234" and item.institution_type is InstitutionType.FOREIGN
    )
    assert foreign.net == foreign.buy - foreign.sell and foreign.is_amount is False
    session = FakeSession()
    repository = MemoryMarketSpotRepository()
    service = MarketSpotIngestionService(session, repository)
    first = await service.synchronize_dataset(provider, "MARKET_INDEXES", target)
    second = await service.synchronize_dataset(provider, "MARKET_INDEXES", target)
    assert (first.inserted_count, second.inserted_count, second.updated_count) == (2, 0, 0)


@pytest.mark.asyncio
async def test_institutional_windows_dealer_subtypes_and_credit() -> None:
    provider = FakeMarketDataProvider()
    repository = MemoryMarketSpotRepository()
    current = date(2026, 5, 18)
    for _ in range(60):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        for dataset, method in DATASETS.items():
            await repository.synchronize(
                dataset, await getattr(provider, method)(current), UUID(int=1)
            )
        current += timedelta(days=1)
    rows = await InstitutionalService(repository).series(
        MarketCode.TWSE, SecurityKey(MarketCode.TWSE, "1234"), 20
    )
    assert len({row["trade_date"] for row in rows}) == 20
    assert {row["dealer_subtype"] for row in rows if row["institution_type"] == "DEALER"} == {
        "PROPRIETARY",
        "HEDGE",
        "TOTAL",
    }
    assert rows[-1]["consecutive_direction_days"] == 20
    credit = await CreditTradingService(repository).series(
        MarketCode.TWSE, SecurityKey(MarketCode.TWSE, "1234"), 60
    )
    assert len(credit["margin"]) == 60 and credit["margin"][-1]["short_margin_ratio"] == "10.0"


@pytest.mark.asyncio
async def test_market_overview_section_unavailable_remains_partial() -> None:
    class LendingUnavailableRepository(MemoryMarketSpotRepository):
        async def lending(self, market, security, start, end):
            raise RuntimeError("official lending unavailable")

    provider = FakeMarketDataProvider()
    repository = LendingUnavailableRepository()
    target = date(2026, 8, 7)
    for dataset, method in DATASETS.items():
        await repository.synchronize(dataset, await getattr(provider, method)(target), UUID(int=1))
    result = await MarketOverviewService(repository, EmptyDerivativesRepository()).overview()
    assert result["meta"]["data_status"] == "PARTIAL"
    assert result["data"]["indexes"]


@pytest.fixture
def market_client():
    provider = FakeMarketDataProvider()
    repository = MemoryMarketSpotRepository()
    securities = InMemorySecurityRepository()
    import asyncio

    asyncio.run(
        securities.synchronize(
            MarketCode.TWSE, asyncio.run(provider.list_securities())[:1], UUID(int=1)
        )
    )
    current = date(2026, 7, 13)
    for _ in range(20):
        while current.weekday() >= 5:
            current += timedelta(days=1)
        for dataset, method in DATASETS.items():
            asyncio.run(
                repository.synchronize(
                    dataset, asyncio.run(getattr(provider, method)(current)), UUID(int=1)
                )
            )
        current += timedelta(days=1)
    app.dependency_overrides[market_spot_repository] = lambda: repository
    app.dependency_overrides[derivatives_repository] = lambda: EmptyDerivativesRepository()
    app.dependency_overrides[security_repository] = lambda: securities
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_market_and_security_apis_decimal_and_errors(market_client) -> None:
    overview = market_client.get("/v1/market/overview")
    assert overview.status_code == 200 and {
        item["code"] for item in overview.json()["data"]["indexes"]
    } == {"TAIEX", "OTC"}
    assert isinstance(overview.json()["data"]["indexes"][0]["close"], str)
    assert market_client.get("/v1/market/indexes/TAIEX").status_code == 200
    assert market_client.get("/v1/market/indexes/BAD").status_code == 404
    assert market_client.get("/v1/market/breadth", params={"market": "TWSE"}).json()["data"]
    assert (
        market_client.get(
            "/v1/market/institutional/spot", params={"market": "TWSE", "window": 5}
        ).status_code
        == 200
    )
    assert market_client.get("/v1/market/credit", params={"market": "TWSE"}).status_code == 200
    vix = market_client.get("/v1/market/volatility")
    assert vix.status_code == 200 and vix.json()["data"] == []
    assert vix.json()["meta"] == {
        "data_status": "UNAVAILABLE",
        "source_type": "OFFICIAL_DOWNLOAD",
        "source_capability": "OFFICIAL_DOWNLOAD",
        "license_status": "PUBLIC_DOWNLOAD_UNVERIFIED_REUSE",
        "automation_allowed": None,
        "storage_allowed": None,
        "redistribution_allowed": None,
    }
    institutional = market_client.get(
        "/v1/securities/1234/institutional", params={"market": "TWSE", "window": 20}
    )
    assert institutional.status_code == 200 and institutional.json()["data"]
    assert (
        market_client.get("/v1/securities/1234/credit", params={"market": "TWSE"}).status_code
        == 200
    )
    assert (
        market_client.get(
            "/v1/market/institutional/spot", params={"market": "TWSE", "window": 3}
        ).status_code
        == 422
    )
