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
    kwargs = {
        "security": SecurityKey(MarketCode.TWSE, "1234"),
        "start_date": date(2026, 8, 3),
        "end_date": date(2026, 8, 7),
    }
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
    items = await base.get_daily_prices(
        security=SecurityKey(MarketCode.TWSE, "1234"),
        start_date=date(2026, 8, 6),
        end_date=date(2026, 8, 7),
    )
    invalid = replace(items[1], high=items[1].low - 1)

    class PartialProvider(FakeMarketDataProvider):
        async def get_daily_prices(self, *args, **kwargs):
            return [items[0], items[0], invalid]

    run = await DailyPriceIngestionService(FakeSession(), MemoryRepository()).synchronize(
        PartialProvider()
    )
    assert run.status == "PARTIAL" and run.inserted_count == 1 and run.rejected_count == 2
    assert validate_price(invalid) == "INVALID_OHLC"


@pytest.mark.asyncio
async def test_expected_non_stock_filtering_and_unknown_code_rejection() -> None:
    base = FakeMarketDataProvider()
    template = (
        await base.get_daily_prices(
            security=SecurityKey(MarketCode.TWSE, "1234"),
            start_date=date(2026, 8, 7),
            end_date=date(2026, 8, 7),
        )
    )[0]

    # 1. TWSE common stock -> 1234
    twse_stock = replace(template, security=SecurityKey(MarketCode.TWSE, "1234"))
    # 2. TPEx common stock -> 5678
    tpex_stock = replace(template, security=SecurityKey(MarketCode.TPEX, "5678"))
    # 3. ETF -> 0050
    etf = replace(template, security=SecurityKey(MarketCode.TWSE, "0050"))
    # 4. Warrant -> 700019
    warrant = replace(template, security=SecurityKey(MarketCode.TPEX, "700019"))
    # 5. Preferred stock -> 1101B
    preferred = replace(template, security=SecurityKey(MarketCode.TWSE, "1101B"))

    class MixProvider(FakeMarketDataProvider):
        async def get_daily_prices(self, *args, **kwargs):
            return [twse_stock, tpex_stock, etf, warrant, preferred]

    # When all common stocks exist in repository:
    class MockStockRepo(MemoryRepository):
        async def synchronize(self, records, run_id):
            return await super().synchronize(records, run_id)

    run = await DailyPriceIngestionService(FakeSession(), MockStockRepo()).synchronize(
        MixProvider()
    )
    assert run.status == "SUCCEEDED"
    assert run.fetched_count == 5
    assert run.inserted_count == 2  # Only 1234 and 5678
    assert run.rejected_count == 0  # ETFs, warrants, and preferred are filtered, not rejected!

    # 6. Unknown common-stock-like code (e.g. 9999) missing from repository -> TRUE REJECTION
    unknown_stock = replace(template, security=SecurityKey(MarketCode.TWSE, "9999"))

    class UnknownStockProvider(FakeMarketDataProvider):
        async def get_daily_prices(self, *args, **kwargs):
            return [twse_stock, etf, unknown_stock]

    class MissingStockRepo(MemoryRepository):
        async def synchronize(self, records, run_id):
            for r in records:
                if r.security.code == "9999":
                    raise LookupError(f"missing security: {r.security.market}:{r.security.code}")
            return await super().synchronize(records, run_id)

    run_unknown = await DailyPriceIngestionService(
        FakeSession(), MissingStockRepo()
    ).synchronize(UnknownStockProvider())
    assert run_unknown.status == "PARTIAL"
    assert run_unknown.fetched_count == 3
    assert run_unknown.inserted_count == 1  # 1234
    assert run_unknown.rejected_count == 1  # 9999 was counted as rejected because it is common-stock-like!
