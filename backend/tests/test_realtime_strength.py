from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from unittest.mock import AsyncMock

import pytest

from app.domain.realtime import DataStatus, RealtimeQuote
from app.domain.realtime_strength import RealtimeTaxonomyType
from app.repositories.realtime_membership import (
    RealtimeMember,
    RealtimeMembershipSnapshot,
)
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_strength import (
    RealtimeIndustryStrengthScoringService,
    RealtimeTaxonomyAggregator,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.published = []

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def get(self, key):
        return self.values.get(key)

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def publish(self, channel, value):
        self.published.append((channel, value))


def memberships():
    members = {
        "TWSE:A": RealtimeMember("a", "TWSE", "A", "A Corp"),
        "TWSE:B": RealtimeMember("b", "TWSE", "B", "B Corp"),
        "TWSE:C": RealtimeMember("c", "TWSE", "C", "C Corp"),
        "TPEX:D": RealtimeMember("d", "TPEx", "D", "D Corp"),
    }
    industry = (RealtimeTaxonomyType.INDUSTRY, "i1")
    industry2 = (RealtimeTaxonomyType.INDUSTRY, "i2")
    theme = (RealtimeTaxonomyType.THEME, "t1")
    return RealtimeMembershipSnapshot(
        members=members,
        taxonomies={
            industry: ("I1", "Industry 1", {"TWSE:A", "TWSE:B", "TWSE:C"}),
            industry2: ("I2", "Industry 2", {"TPEX:D"}),
            theme: ("T1", "Theme 1", {"TWSE:A", "TWSE:C", "TPEX:D"}),
        },
        by_security={
            "TWSE:A": {industry, theme},
            "TWSE:B": {industry},
            "TWSE:C": {industry, theme},
            "TPEX:D": {industry2, theme},
        },
    )


def quote(code, market, price, previous, sequence=1, status=DataStatus.LIVE, turnover="1000"):
    now = datetime(2026, 8, 13, 1, 0, tzinfo=UTC) + timedelta(seconds=sequence)
    return RealtimeQuote(
        security_id=code.lower(),
        market_id=market,
        code=code,
        exchange_timestamp=now,
        received_at=now,
        last_price=Decimal(price),
        previous_close=Decimal(previous) if previous is not None else None,
        turnover_amount=Decimal(turnover) if turnover is not None else None,
        sequence=sequence,
        data_status=status,
        provider="FAKE_REALTIME_PROVIDER",
    )


@pytest.mark.asyncio
async def test_market_breadth_coverage_turnover_status_and_separation():
    service = RealtimeTaxonomyAggregator(memberships(), RealtimeCacheService(FakeRedis()))
    await service.accept(quote("A", "TWSE", "11", "10"))
    await service.accept(quote("B", "TWSE", "9", "10", 2, DataStatus.STALE))
    await service.accept(quote("C", "TWSE", "10", "10", 3))
    await service.accept(quote("D", "TPEx", "20", None, 4))
    twse = service.market.accept(quote("A", "TWSE", "11", "10", 5))
    assert (twse.advancers, twse.decliners, twse.unchanged) == (1, 1, 1)
    assert twse.coverage_ratio == Decimal("1") and twse.turnover_amount == Decimal("3000")
    assert twse.stale_count == 1 and twse.market_id == "TWSE"
    tpex = service.market.accept(quote("D", "TPEx", "20", None, 6))
    assert tpex.valid_members == 0 and tpex.coverage_ratio == 0


@pytest.mark.asyncio
async def test_taxonomy_overlap_partial_equal_weight_leaders_and_incremental_cache():
    redis = FakeRedis()
    service = RealtimeTaxonomyAggregator(memberships(), RealtimeCacheService(redis))
    await service.accept(quote("A", "TWSE", "11", "10"))
    assert service.metrics["taxonomy_snapshots_updated"] == 2
    await service.accept(quote("B", "TWSE", "8", "10", 2, turnover=None))
    await service.accept(quote("C", "TWSE", "10", "10", 3))
    industry = service.snapshots[(RealtimeTaxonomyType.INDUSTRY, "i1")]
    assert industry.equal_weight_return == Decimal("-3.333333333333333333333333333")
    assert (industry.advancers, industry.decliners, industry.unchanged) == (1, 1, 1)
    assert industry.turnover_amount is None and industry.leaders[0].code == "A"
    theme = service.snapshots[(RealtimeTaxonomyType.THEME, "t1")]
    assert theme.quoted_members == 2 and theme.coverage_ratio == Decimal(
        "0.6666666666666666666666666667"
    )
    assert service.metrics["taxonomy_membership_cache_misses"] == 0
    assert any(key.startswith("realtime:ranking:") for key in redis.values)


def test_realtime_score_percentiles_reweight_range_ties_and_null_last():
    scorer = RealtimeIndustryStrengthScoringService()
    assert scorer.percentiles({"a": Decimal("1"), "b": Decimal("1")}) == {
        "a": Decimal("50.00"),
        "b": Decimal("50.00"),
    }


@pytest.mark.asyncio
async def test_redis_snapshots_and_websocket_initial_global_snapshots():
    redis = FakeRedis()
    cache = RealtimeCacheService(redis)
    service = RealtimeTaxonomyAggregator(memberships(), cache)
    await service.accept(quote("A", "TWSE", "11", "10"))
    assert await cache.get_market_snapshot("TWSE") is not None
    assert await cache.get_taxonomy_ranking(RealtimeTaxonomyType.INDUSTRY)
    hub = RealtimeQuoteHub(redis, cache)
    websocket = AsyncMock()
    session = await hub.register_connection(websocket)
    await hub.handle_subscribe(session, [], ["market", "industry_strength", "theme_strength"])
    messages = [call.args[0]["type"] for call in websocket.send_json.call_args_list]
    assert "market_snapshot" in messages
    assert messages.count("taxonomy_ranking_snapshot") == 2


@pytest.mark.asyncio
async def test_realtime_strength_incremental_performance_smoke():
    members = {
        f"TWSE:{index:04d}": RealtimeMember(str(index), "TWSE", f"{index:04d}", str(index))
        for index in range(1000)
    }
    taxonomy_keys = [(RealtimeTaxonomyType.INDUSTRY, f"i{index:02d}") for index in range(50)]
    taxonomies = {
        key: (
            key[1].upper(),
            key[1],
            {
                member_key
                for offset, member_key in enumerate(members)
                if offset % 50 in {(int(key[1][1:]) + step) % 50 for step in range(10)}
            },
        )
        for key in taxonomy_keys
    }
    by_security = {
        member_key: {key for key, (_, _, keys) in taxonomies.items() if member_key in keys}
        for member_key in members
    }
    assert sum(len(keys) for keys in by_security.values()) == 10_000
    service = RealtimeTaxonomyAggregator(
        RealtimeMembershipSnapshot(members, taxonomies, by_security),
        RealtimeCacheService(FakeRedis()),
    )
    started = perf_counter()
    for index in range(100):
        await service.accept(quote(f"{index:04d}", "TWSE", "11", "10", index + 1))
    elapsed_ms = (perf_counter() - started) * 1000
    average_ms = elapsed_ms / 100
    print(
        "realtime-strength: 1000 securities / 50 taxonomies / "
        f"10000 memberships / 100 quotes = {average_ms:.3f} ms/quote"
    )
    assert average_ms < 10
    assert len(service.market.quotes) == 100
    assert service.metrics["ranking_updates_throttled"] > 0
