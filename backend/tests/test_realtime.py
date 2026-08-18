import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from app.adapters.fake_realtime_provider import (
    FakeRealtimeProvider,
    UnconfiguredRealtimeProvider,
)
from app.domain.realtime import (
    DataStatus,
    LicenseStatus,
    RealtimeQuote,
)
from app.main import app
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_provider_manager import RealtimeProviderManager


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.published = []

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.store[key] = value

    async def mget(self, keys: list[str]):
        return [self.store.get(k) for k in keys]

    async def publish(self, channel: str, message: str):
        self.published.append((channel, message))

    def pubsub(self):
        fake_pubsub = AsyncMock()
        fake_pubsub.subscribe = AsyncMock()
        fake_pubsub.unsubscribe = AsyncMock()

        async def empty_generator():
            if False:
                yield None

        fake_pubsub.listen = empty_generator
        return fake_pubsub


@pytest.mark.asyncio
async def test_fake_provider_capabilities():
    provider = FakeRealtimeProvider()
    caps = await provider.get_capabilities()
    assert caps.realtime_available is True
    assert caps.license_status == LicenseStatus.AUTHORIZED
    assert caps.is_live_eligible is True


@pytest.mark.asyncio
async def test_unconfigured_provider_capabilities():
    provider = UnconfiguredRealtimeProvider()
    caps = await provider.get_capabilities()
    assert caps.realtime_available is False
    assert caps.license_status == LicenseStatus.UNCONFIGURED
    assert caps.is_live_eligible is False


@pytest.mark.asyncio
async def test_redis_cache_ordering_and_ttl():
    fake_redis = FakeRedis()
    cache = RealtimeCacheService(fake_redis)

    now = datetime.now(UTC)
    q1 = RealtimeQuote(
        security_id="sec_2330",
        market_id="TWSE",
        code="2330",
        exchange_timestamp=now,
        received_at=now,
        last_price=Decimal("950.00"),
        sequence=1,
        data_status=DataStatus.LIVE,
    )

    q2_older = RealtimeQuote(
        security_id="sec_2330",
        market_id="TWSE",
        code="2330",
        exchange_timestamp=now - timedelta(seconds=10),
        received_at=now - timedelta(seconds=10),
        last_price=Decimal("940.00"),
        sequence=1,  # Same sequence
        data_status=DataStatus.LIVE,
    )

    q3_newer = RealtimeQuote(
        security_id="sec_2330",
        market_id="TWSE",
        code="2330",
        exchange_timestamp=now + timedelta(seconds=1),
        received_at=now + timedelta(seconds=1),
        last_price=Decimal("955.00"),
        sequence=2,  # Higher sequence
        data_status=DataStatus.LIVE,
    )

    # Save q1
    res1 = await cache.save_and_publish_quote(q1)
    assert res1 is True
    fetched1 = await cache.get_quote("TWSE", "2330")
    assert fetched1.last_price == Decimal("950.00")

    # Save q2_older -> Should be rejected
    res2 = await cache.save_and_publish_quote(q2_older)
    assert res2 is False
    fetched2 = await cache.get_quote("TWSE", "2330")
    assert fetched2.last_price == Decimal("950.00")

    # Save q3_newer -> Should overwrite
    res3 = await cache.save_and_publish_quote(q3_newer)
    assert res3 is True
    fetched3 = await cache.get_quote("TWSE", "2330")
    assert fetched3.last_price == Decimal("955.00")


@pytest.mark.asyncio
async def test_hub_subscription_limits_and_routing():
    fake_redis = FakeRedis()
    cache = RealtimeCacheService(fake_redis)
    hub = RealtimeQuoteHub(fake_redis, cache, max_subscriptions_per_conn=2)

    mock_ws = AsyncMock()
    session = await hub.register_connection(mock_ws)

    # Subscribe 2 securities (at max limit)
    await hub.handle_subscribe(
        session,
        [{"market": "TWSE", "code": "2330"}, {"market": "TWSE", "code": "2317"}],
    )
    assert len(session.subscriptions) == 2

    # Subscribe 3rd security -> Should be rejected with error message
    await hub.handle_subscribe(session, [{"market": "TWSE", "code": "2454"}])
    assert len(session.subscriptions) == 2
    mock_ws.send_json.assert_called_with(
        {
            "type": "error",
            "version": 1,
            "message": "Subscription limit reached (2)",
        }
    )

    # Unsubscribe one
    await hub.handle_unsubscribe(session, [{"market": "TWSE", "code": "2330"}])
    assert len(session.subscriptions) == 1

    await hub.unregister_connection(session)
    assert len(hub.sessions) == 0


def test_http_quote_snapshot_api_endpoints():
    fake_redis = FakeRedis()
    cache = RealtimeCacheService(fake_redis)

    app.state.redis = fake_redis
    app.state.realtime_cache_service = cache

    client = TestClient(app)

    # 404 for non-cached quote
    resp = client.get("/v1/quotes/TWSE/2330")
    assert resp.status_code == 404

    # Populate cache
    now = datetime.now(UTC)
    q = RealtimeQuote(
        security_id="sec_2330",
        market_id="TWSE",
        code="2330",
        exchange_timestamp=now,
        received_at=now,
        last_price=Decimal("950.00"),
        data_status=DataStatus.LIVE,
    )
    asyncio.run(cache.save_and_publish_quote(q))

    # GET snapshot -> 200 OK
    resp_ok = client.get("/v1/quotes/TWSE/2330")
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["code"] == "2330"
    assert data["last_price"] == "950.00"

    # POST batch -> 200 OK
    resp_batch = client.post(
        "/v1/quotes/batch",
        json={
            "targets": [
                {"market": "TWSE", "code": "2330"},
                {"market": "TWSE", "code": "9999"},
            ]
        },
    )
    assert resp_batch.status_code == 200
    batch_data = resp_batch.json()
    assert len(batch_data) == 2
    assert batch_data[0]["code"] == "2330"
    assert batch_data[1] is None


@pytest.mark.asyncio
async def test_unconfigured_provider_manager_start_and_no_busy_loop():
    fake_redis = FakeRedis()
    cache = RealtimeCacheService(fake_redis)
    hub = RealtimeQuoteHub(fake_redis, cache)
    provider = UnconfiguredRealtimeProvider()
    manager = RealtimeProviderManager(provider, cache, hub)

    # start() must return promptly without spawning an ingestion loop task
    await manager.start()
    assert manager._running is True
    assert manager._ingestion_task is None
    assert hub.provider_status == "UNAVAILABLE"

    # capabilities must remain unconfigured
    caps = await manager.get_capabilities()
    assert caps.realtime_available is False
    assert caps.configured is False
    assert caps.license_status == LicenseStatus.UNCONFIGURED

    await manager.stop()
    assert manager._running is False


@pytest.mark.asyncio
async def test_unconfigured_provider_stream_quotes_does_not_busy_loop():
    provider = UnconfiguredRealtimeProvider()
    stream = provider.stream_quotes()

    # The stream should block waiting for data or cancellation, not immediately terminate or spin
    task = asyncio.create_task(stream.__anext__())
    done, pending = await asyncio.wait([task], timeout=0.05)
    assert len(done) == 0
    assert len(pending) == 1
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, StopAsyncIteration):
        pass


def test_production_startup_lifespan_and_health_with_unconfigured_realtime(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_SECRET", "test-secret-at-least-32-chars-long-123456")
    from app.core.settings import get_settings

    get_settings.cache_clear()

    # With APP_ENV=production, main uses UnconfiguredRealtimeProvider
    with TestClient(app) as client:
        health_resp = client.get("/v1/health")
        assert health_resp.status_code == 200
        assert health_resp.json() == {"status": "ok"}

        readiness_resp = client.get("/v1/production-readiness")
        assert readiness_resp.status_code == 200
        readiness_data = readiness_resp.json()
        assert "components" in readiness_data
        assert "realtime_provider" in readiness_data["components"]
        assert readiness_data["components"]["realtime_provider"]["status"] == "UNCONFIGURED"

    get_settings.cache_clear()

