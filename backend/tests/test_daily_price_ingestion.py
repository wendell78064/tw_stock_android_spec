from dataclasses import replace
from datetime import date

import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode
from app.services.daily_price_ingestion import DailyPriceIngestionService, validate_price
from tests.fakes import FakeSession


class MemoryRepository:
    def __init__(self):
        self.items = {}

    async def synchronize(self, records, run_id):
        del run_id
        inserted = updated = 0
        for item in records:
            key = (item.security, item.trade_date)
            if key not in self.items:
                inserted += 1
            elif self.items[key] != item:
                updated += 1
            self.items[key] = item
        return inserted, updated


@pytest.mark.asyncio
async def test_insert_update_revision_idempotency_and_range_backfill() -> None:
    provider = FakeMarketDataProvider()
    repository = MemoryRepository()
    service = DailyPriceIngestionService(FakeSession(), repository)
    kwargs = {"security": SecurityKey(MarketCode.TWSE, "1234"),
              "start_date": date(2026, 8, 3), "end_date": date(2026, 8, 7)}
    first = await service.synchronize(provider, **kwargs)
    second = await service.synchronize(provider, **kwargs)
    assert first.inserted_count == 5 and second.inserted_count + second.updated_count == 0

    original = await provider.get_daily_prices(**kwargs)
    revised = replace(original[0], close=original[0].close + 1, source_revision="fixture-v2")

    class RevisedProvider(FakeMarketDataProvider):
        async def get_daily_prices(self, *args, **values):
            return [revised, *original[1:]]

    third = await service.synchronize(RevisedProvider(), **kwargs)
    assert third.updated_count == 1


@pytest.mark.asyncio
async def test_duplicate_and_invalid_ohlc_are_partial_not_batch_failure() -> None:
    base = FakeMarketDataProvider()
    items = await base.get_daily_prices(security=SecurityKey(MarketCode.TWSE, "1234"),
        start_date=date(2026, 8, 6), end_date=date(2026, 8, 7))
    invalid = replace(items[1], high=items[1].low - 1)

    class PartialProvider(FakeMarketDataProvider):
        async def get_daily_prices(self, *args, **kwargs):
            return [items[0], items[0], invalid]

    run = await DailyPriceIngestionService(
        FakeSession(), MemoryRepository()
    ).synchronize(PartialProvider())
    assert run.status == "PARTIAL" and run.inserted_count == 1 and run.rejected_count == 2
    assert validate_price(invalid) == "INVALID_OHLC"
