from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import security_repository, watchlist_repository
from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode
from app.domain.watchlist import Watchlist, WatchlistItem
from app.main import app
from app.services.watchlist import WatchlistService


class MemoryWatchlists:
    def __init__(self):
        self.groups = {}
        self.items = {}
        self.overview_calls = 0

    async def list_watchlists(self):
        return sorted(self.groups.values(), key=lambda x: x.sort_order)

    async def get_watchlist(self, value):
        return self.groups.get(value)

    async def create_watchlist(self, name):
        now = datetime.now(UTC)
        row = Watchlist(uuid4(), name, len(self.groups), now, now)
        self.groups[row.id] = row
        return row

    async def rename_watchlist(self, value, name):
        old = self.groups.get(value)
        if not old:
            return None
        row = Watchlist(old.id, name, old.sort_order, old.created_at, datetime.now(UTC))
        self.groups[value] = row
        return row

    async def delete_watchlist(self, value):
        found = self.groups.pop(value, None) is not None
        self.items = {key: row for key, row in self.items.items() if row.watchlist_id != value}
        return found

    async def reorder_watchlists(self, orders):
        if any(value not in self.groups for value, _ in orders):
            return False
        for value, order in orders:
            old = self.groups[value]
            self.groups[value] = Watchlist(old.id, old.name, order, old.created_at, old.updated_at)
        return True

    async def list_items(self, value):
        return sorted(
            [row for row in self.items.values() if row.watchlist_id == value],
            key=lambda x: x.sort_order,
        )

    async def get_item(self, group, value):
        return self.items.get(value)

    async def add_item(self, group, security):
        now = datetime.now(UTC)
        source = SECURITIES[security]
        row = WatchlistItem(
            uuid4(),
            group,
            security,
            source.code,
            source.name,
            source.market,
            len(await self.list_items(group)),
            None,
            None,
            None,
            None,
            now,
            now,
        )
        self.items[row.id] = row
        return row

    async def update_item(self, group, value, **changes):
        old = self.items.get(value)
        if not old or old.watchlist_id != group:
            return None
        data = old.__dict__ | changes | {"updated_at": datetime.now(UTC)}
        row = WatchlistItem(**data)
        self.items[value] = row
        return row

    async def delete_item(self, group, value):
        row = self.items.get(value)
        if not row or row.watchlist_id != group:
            return False
        del self.items[value]
        return True

    async def reorder_items(self, group, orders):
        if any(
            value not in self.items or self.items[value].watchlist_id != group
            for value, _ in orders
        ):
            return False
        for value, order in orders:
            await self.update_item(group, value, sort_order=order)
        return True

    async def overview(self, group):
        self.overview_calls += 1
        return self.rows


class Securities:
    async def find_by_code(self, code, market):
        return [
            row
            for row in SECURITIES.values()
            if row.code == code and (market is None or row.market == market)
        ]


S1, S2, S3 = uuid4(), uuid4(), uuid4()
SECURITIES = {
    S1: SimpleNamespace(id=S1, code="1234", name="測試一", market=MarketCode.TWSE),
    S2: SimpleNamespace(id=S2, code="5678", name="測試二", market=MarketCode.TWSE),
    S3: SimpleNamespace(id=S3, code="1234", name="測試三", market=MarketCode.TPEX),
}


@pytest.fixture
def setup():
    repository = MemoryWatchlists()
    repository.rows = []
    return repository, WatchlistService(repository, Securities())


@pytest.mark.asyncio
async def test_group_create_rename_delete_and_trim(setup):
    repo, service = setup
    row = await service.create("  我的群組 ")
    assert row.name == "我的群組"
    assert (await service.rename(row.id, "新版")).name == "新版"
    await service.delete(row.id)
    assert not repo.groups


@pytest.mark.asyncio
async def test_delete_nonempty_cascades_items(setup):
    repo, service = setup
    group = await service.create("a")
    await service.add_security(group.id, "5678", None)
    await service.delete(group.id)
    assert not repo.items


@pytest.mark.asyncio
async def test_add_duplicate_remove_and_same_security_in_two_groups(setup):
    repo, service = setup
    first = await service.create("a")
    second = await service.create("b")
    one = await service.add_security(first.id, "5678", None)
    await service.add_security(second.id, "5678", None)
    with pytest.raises(AppError) as error:
        await service.add_security(first.id, "5678", None)
    assert error.value.code == "WATCHLIST_ITEM_EXISTS"
    await service.remove(first.id, one.id)
    assert len(repo.items) == 1


@pytest.mark.asyncio
async def test_unknown_and_ambiguous_security(setup):
    _, service = setup
    group = await service.create("a")
    with pytest.raises(AppError) as error:
        await service.add_security(group.id, "0000", None)
    assert error.value.code == "SECURITY_NOT_FOUND"
    with pytest.raises(AppError) as error:
        await service.add_security(group.id, "1234", None)
    assert error.value.code == "AMBIGUOUS_SECURITY"


@pytest.mark.asyncio
async def test_update_note_and_prices(setup):
    _, service = setup
    group = await service.create("a")
    row = await service.add_security(group.id, "5678", None)
    result = await service.update_item(
        group.id, row.id, " note ", Decimal("20"), Decimal("8"), Decimal("12")
    )
    assert (result.note, result.target_price, result.stop_price, result.add_price) == (
        "note",
        Decimal("20"),
        Decimal("8"),
        Decimal("12"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("field", [0, 1, 2])
async def test_invalid_prices_rejected(setup, field):
    _, service = setup
    group = await service.create("a")
    row = await service.add_security(group.id, "5678", None)
    values = [None, None, None]
    values[field] = Decimal("0")
    with pytest.raises(AppError) as error:
        await service.update_item(group.id, row.id, None, *values)
    assert error.value.code == "WATCHLIST_INVALID_PRICE"


@pytest.mark.asyncio
async def test_group_and_item_batch_reorder(setup):
    repo, service = setup
    a = await service.create("a")
    b = await service.create("b")
    await service.reorder_groups([(a.id, 1), (b.id, 0)])
    assert (await repo.list_watchlists())[0].id == b.id
    one = await service.add_security(a.id, "5678", None)
    two = await service.add_security(a.id, "1234", MarketCode.TWSE)
    await service.reorder_items(a.id, [(one.id, 1), (two.id, 0)])
    assert (await repo.list_items(a.id))[0].id == two.id


@pytest.mark.asyncio
async def test_overview_statuses_and_single_bulk_call(setup):
    repo, service = setup
    group = await service.create("a")
    repo.rows = [
        dict(
            close=Decimal("10"),
            ma20=Decimal("9"),
            ma60=None,
            price_status=DataStatus.FINAL,
            technical_status=DataStatus.FINAL,
            credit_status=None,
        )
    ]
    rows = await service.overview(group.id)
    assert rows[0]["data_status"] == DataStatus.PARTIAL and rows[0]["price_above_ma20"] is True
    assert repo.overview_calls == 1


@pytest.mark.asyncio
async def test_missing_price_is_unavailable(setup):
    repo, service = setup
    group = await service.create("a")
    repo.rows = [
        dict(
            close=None,
            ma20=None,
            ma60=None,
            price_status=None,
            technical_status=None,
            credit_status=None,
        )
    ]
    assert (await service.overview(group.id))[0]["data_status"] == DataStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_fifty_security_overview_uses_one_repository_query(setup):
    repo, service = setup
    group = await service.create("a")
    repo.rows = [
        dict(
            close=Decimal("10"),
            ma20=None,
            ma60=None,
            price_status=DataStatus.FINAL,
            technical_status=None,
            credit_status=None,
        )
        for _ in range(50)
    ]
    assert len(await service.overview(group.id)) == 50 and repo.overview_calls == 1


def test_watchlist_api_smoke():
    repository = MemoryWatchlists()
    app.dependency_overrides[watchlist_repository] = lambda: repository
    app.dependency_overrides[security_repository] = lambda: Securities()
    try:
        with TestClient(app) as client:
            created = client.post("/v1/watchlists", json={"name": " 測試自選 "})
            assert created.status_code == 201 and created.json()["data"]["name"] == "測試自選"
            group_id = created.json()["data"]["id"]
            added = client.post(
                f"/v1/watchlists/{group_id}/items",
                json={"security_code": "5678", "market": "TWSE"},
            )
            assert added.status_code == 201 and added.json()["data"]["security_code"] == "5678"
            duplicate = client.post(
                f"/v1/watchlists/{group_id}/items",
                json={"security_code": "5678", "market": "TWSE"},
            )
            assert duplicate.status_code == 409
            assert duplicate.json()["error"]["code"] == "WATCHLIST_ITEM_EXISTS"
    finally:
        app.dependency_overrides.clear()
