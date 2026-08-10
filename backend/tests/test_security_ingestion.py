from dataclasses import replace
from uuid import uuid4

import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.domain.security import MarketCode
from app.services.security_ingestion import SecurityIngestionService
from tests.fakes import FakeSession, InMemorySecurityRepository


@pytest.mark.asyncio
async def test_ingestion_insert_update_idempotency_and_inactive() -> None:
    provider = FakeMarketDataProvider()
    records = await provider.list_securities()
    repository = InMemorySecurityRepository()
    session = FakeSession()
    service = SecurityIngestionService(session, repository)

    first = await service.synchronize(provider)
    assert sum(run.inserted_count for run in first) == 2
    second = await service.synchronize(provider)
    assert sum(run.inserted_count + run.updated_count for run in second) == 0

    changed = replace(records[0], name="測試科技更名")
    inserted, updated, inactive = await repository.synchronize(MarketCode.TWSE, [changed], uuid4())
    assert (inserted, updated, inactive) == (0, 1, 0)
    _, _, inactive = await repository.synchronize(MarketCode.TWSE, [], uuid4())
    assert inactive == 1


@pytest.mark.asyncio
async def test_duplicate_same_market_rejected_but_cross_market_allowed() -> None:
    records = await FakeMarketDataProvider().list_securities()
    repository = InMemorySecurityRepository()
    with pytest.raises(ValueError):
        await repository.synchronize(MarketCode.TWSE, [records[0], records[0]], uuid4())
    cross_market = replace(records[1], code=records[0].code)
    await repository.synchronize(MarketCode.TWSE, [records[0]], uuid4())
    await repository.synchronize(MarketCode.TPEX, [cross_market], uuid4())
    assert len(await repository.find_by_code(records[0].code, None)) == 2
