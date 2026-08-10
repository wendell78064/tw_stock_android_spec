from dataclasses import replace
from uuid import UUID, uuid4

from app.domain.security import MarketCode, Security, SecurityRecord, SecurityStatus, SecurityType


class InMemorySecurityRepository:
    def __init__(self):
        self.items: dict[tuple[MarketCode, str], Security] = {}

    async def synchronize(
        self, market: MarketCode, records: list[SecurityRecord], run_id: UUID
    ) -> tuple[int, int, int]:
        del run_id
        seen: set[str] = set()
        inserted = updated = inactive = 0
        for record in records:
            if record.code in seen:
                raise ValueError("duplicate security")
            seen.add(record.code)
            key = (market, record.code)
            existing = self.items.get(key)
            item = Security(
                id=existing.id if existing else uuid4(),
                market=market,
                code=record.code,
                name=record.name,
                security_type=record.security_type,
                status=record.status,
                is_active=record.status is SecurityStatus.ACTIVE,
                listing_date=record.listing_date,
                primary_industry=record.industry.name if record.industry else None,
                source_code=record.source_code,
                as_of=record.as_of,
                received_at=record.received_at,
                data_status=record.data_status,
            )
            if existing is None:
                inserted += 1
            elif existing != item:
                updated += 1
            self.items[key] = item
        for key, item in list(self.items.items()):
            if key[0] is market and key[1] not in seen and item.is_active:
                self.items[key] = replace(item, status=SecurityStatus.INACTIVE, is_active=False)
                inactive += 1
        return inserted, updated, inactive

    async def search(self, query: str, market: MarketCode | None, limit: int) -> list[Security]:
        matches = [
            item
            for item in self.items.values()
            if item.is_active
            and (market is None or item.market is market)
            and (item.code.startswith(query) or query in item.name)
            and item.security_type is SecurityType.COMMON_STOCK
        ]
        return sorted(matches, key=lambda item: (item.code != query, item.code))[:limit]

    async def find_by_code(self, code: str, market: MarketCode | None) -> list[Security]:
        return [
            item
            for item in self.items.values()
            if item.code == code and item.is_active and (market is None or item.market is market)
        ]


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None

    async def commit(self):
        return None

    async def rollback(self):
        return None
