from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.core.dependencies import security_repository
from app.domain.security import MarketCode
from app.main import app
from tests.fakes import InMemorySecurityRepository


@pytest.fixture
def repository():
    return InMemorySecurityRepository()


@pytest.fixture
def client(repository):
    app.dependency_overrides[security_repository] = lambda: repository
    try:
        with TestClient(app) as value:
            yield value
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_exact_prefix_chinese_and_market_filter(client, repository) -> None:
    records = await FakeMarketDataProvider().list_securities()
    await repository.synchronize(MarketCode.TWSE, records[:1], uuid4())
    await repository.synchronize(MarketCode.TPEX, records[1:], uuid4())
    assert (
        client.get("/v1/securities/search", params={"q": "1234"}).json()["data"][0]["code"]
        == "1234"
    )
    assert (
        client.get("/v1/securities/search", params={"q": "12"}).json()["data"][0]["code"] == "1234"
    )
    assert (
        client.get("/v1/securities/search", params={"q": "科技"}).json()["data"][0]["name"]
        == "測試科技"
    )
    assert (
        client.get("/v1/securities/search", params={"q": "測試", "market": "TPEX"}).json()["data"]
        == []
    )


@pytest.mark.asyncio
async def test_detail_404_and_ambiguous_security(client, repository) -> None:
    assert client.get("/v1/securities/9999").status_code == 404
    records = await FakeMarketDataProvider().list_securities()
    await repository.synchronize(MarketCode.TWSE, records[:1], uuid4())
    await repository.synchronize(MarketCode.TPEX, [replace(records[1], code="1234")], uuid4())
    ambiguous = client.get("/v1/securities/1234")
    assert ambiguous.status_code == 409
    assert ambiguous.json()["error"]["code"] == "AMBIGUOUS_SECURITY"
    selected = client.get("/v1/securities/1234", params={"market": "TWSE"})
    assert selected.status_code == 200
    assert selected.json()["data"]["market"] == "TWSE"
