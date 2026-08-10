from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.core.dependencies import price_repository, security_repository
from app.domain.market_data import DataStatus
from app.domain.pricing import CandleInterval, PriceBasis, SecurityKey, TechnicalSnapshot
from app.domain.security import MarketCode
from app.main import app
from app.services.candle_aggregation import CandleAggregationService
from app.services.technical_indicators import ALGORITHM_VERSION, TechnicalIndicatorService
from tests.fakes import InMemorySecurityRepository


class MemoryPriceRepository:
    def __init__(self, records):
        self.records = records
        self.snapshots = []

    async def synchronize(self, records, run_id: UUID):
        del run_id
        self.records = records
        return len(records), 0

    async def list_prices(self, security, start_date, end_date):
        return [
            item
            for item in self.records
            if item.security == security
            and (start_date is None or item.trade_date >= start_date)
            and (end_date is None or item.trade_date <= end_date)
        ]

    async def replace_technicals(self, security, basis, snapshots):
        self.snapshots = snapshots

    async def list_technicals(self, security, basis, start_date, end_date):
        return [
            item
            for item in self.snapshots
            if item.security == security and item.price_basis == basis
        ]


@pytest.fixture
def price_client():
    provider = FakeMarketDataProvider()
    records = __import__("asyncio").run(
        provider.get_daily_prices(
            security=SecurityKey(MarketCode.TWSE, "1234"),
            start_date=date(2025, 1, 1),
            end_date=date(2026, 8, 7),
        )
    )
    securities = InMemorySecurityRepository()
    __import__("asyncio").run(
        securities.synchronize(
            MarketCode.TWSE, __import__("asyncio").run(provider.list_securities())[:1], UUID(int=1)
        )
    )
    prices = MemoryPriceRepository(records)
    candles = CandleAggregationService().aggregate(records, CandleInterval.DAY, PriceBasis.ADJUSTED)
    series = TechnicalIndicatorService().calculate(candles)
    prices.snapshots = [
        TechnicalSnapshot(
            SecurityKey(MarketCode.TWSE, "1234"),
            candle.trade_date,
            PriceBasis.ADJUSTED,
            values,
            ALGORITHM_VERSION,
            datetime(2026, 8, 7, tzinfo=UTC),
            datetime(2026, 8, 7, tzinfo=UTC),
            DataStatus.FINAL,
        )
        for candle, values in zip(candles, series.values, strict=True)
    ]
    app.dependency_overrides[security_repository] = lambda: securities
    app.dependency_overrides[price_repository] = lambda: prices
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_daily_weekly_monthly_raw_adjusted_and_decimal_serialization(price_client) -> None:
    raw = price_client.get(
        "/v1/securities/1234/candles",
        params={"market": "TWSE", "range": "1D", "interval": "1d", "adjustment": "RAW"},
    )
    assert raw.status_code == 200 and len(raw.json()["data"]) == 1
    assert isinstance(raw.json()["data"][0]["close"], str)
    for interval in ("1w", "1mo"):
        response = price_client.get(
            "/v1/securities/1234/candles",
            params={
                "market": "TWSE",
                "range": "5Y",
                "interval": interval,
                "adjustment": "ADJUSTED",
            },
        )
        assert response.status_code == 200 and response.json()["data"]


def test_technicals_and_validation_errors(price_client) -> None:
    response = price_client.get(
        "/v1/securities/1234/technicals",
        params={"market": "TWSE", "price_basis": "ADJUSTED", "indicators": "MA20,RSI14,MACD,KD_K"},
    )
    assert response.status_code == 200
    assert {item["name"] for item in response.json()["data"][-1]["indicators"]} == {
        "MA20",
        "RSI14",
        "MACD",
        "KD_K",
    }
    assert (
        price_client.get(
            "/v1/securities/1234/candles", params={"market": "BAD", "range": "1Y", "interval": "1d"}
        ).status_code
        == 422
    )
    assert (
        price_client.get(
            "/v1/securities/1234/candles",
            params={"market": "TWSE", "range": "BAD", "interval": "1d"},
        ).status_code
        == 422
    )
    assert (
        price_client.get(
            "/v1/securities/1234/candles",
            params={"market": "TWSE", "range": "1Y", "interval": "1m"},
        ).status_code
        == 422
    )
    assert (
        price_client.get(
            "/v1/securities/9999/candles",
            params={"market": "TWSE", "range": "1Y", "interval": "1d"},
        ).status_code
        == 404
    )
