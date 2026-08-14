from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.domain.ai import (
    AnalysisType,
    StatementType,
)
from app.domain.realtime import LicenseStatus, ProviderCapabilities, SourceType
from app.repositories.models import (
    MarketModel,
    PortfolioModel,
    SecurityModel,
    UserDeviceModel,
)
from app.services.ai_grounding import (
    AIAnalysisService,
    FakeAIProvider,
    GroundingBuilder,
    UnconfiguredAIProvider,
)
from app.services.production_readiness import (
    ProductionReadinessService,
    RealtimeProductionGate,
)
from app.services.push_notifications import (
    FakePushProvider,
    PushNotificationService,
)


class FakeSession:
    def __init__(self):
        self.objects = {}
        self.added = []

    async def scalar(self, statement):
        user_id = None
        target_id = None
        key = None
        for crit in getattr(statement, "_where_criteria", ()):
            col_name = getattr(getattr(crit, "left", None), "name", None)
            val = getattr(getattr(crit, "right", None), "value", None)
            if col_name == "user_id":
                user_id = val
            elif col_name in ("portfolio_id", "id"):
                target_id = val
            elif col_name == "key":
                key = val

        entity = getattr(statement, "column_descriptions", [{}])[0].get("entity")
        if entity:
            for (kind, _), value in self.objects.items():
                if kind is entity:
                    if user_id is not None and getattr(value, "user_id", None) != user_id:
                        continue
                    if target_id is not None and getattr(value, "id", None) != target_id:
                        continue
                    if key is not None and getattr(value, "key", None) != key:
                        continue
                    return value
        return None

    async def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        user_id = None
        portfolio_id = None
        key = None
        for crit in getattr(statement, "_where_criteria", ()):
            col_name = getattr(getattr(crit, "left", None), "name", None)
            val = getattr(getattr(crit, "right", None), "value", None)
            if col_name == "user_id":
                user_id = val
            elif col_name == "portfolio_id":
                portfolio_id = val
            elif col_name == "key":
                key = val

        values = [
            value
            for (kind, _), value in self.objects.items()
            if kind is entity
            and (user_id is None or getattr(value, "user_id", None) == user_id)
            and (portfolio_id is None or getattr(value, "portfolio_id", None) == portfolio_id)
            and (key is None or getattr(value, "key", None) == key)
        ]
        return SimpleNamespace(all=lambda: values, first=lambda: values[0] if values else None)

    async def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def add(self, value):
        self.added.append(value)
        if hasattr(value, "id"):
            self.objects[(type(value), value.id)] = value

    async def flush(self):
        pass

    async def commit(self):
        pass

    async def execute(self, stmt):
        return SimpleNamespace(scalar=lambda: 1)


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, val, ex=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = val
        return True

    async def ping(self):
        return True


@pytest.mark.asyncio
async def test_ai_market_and_security_grounding():
    session = FakeSession()
    sec_id = uuid4()
    market_id = uuid4()

    m = MarketModel(id=market_id, code="TWSE", name="Taiwan Stock Exchange")
    sec = SimpleNamespace(
        id=sec_id,
        market_id=market_id,
        code="2330",
        name="TSMC",
        is_active=True,
    )
    session.objects[(MarketModel, market_id)] = m
    session.objects[(SecurityModel, sec_id)] = sec

    builder = GroundingBuilder(session)

    # 1. Market Grounding
    market_pkg = await builder.build_market_grounding("req-1")
    assert market_pkg.analysis_type == AnalysisType.MARKET_SUMMARY
    assert any(f.key == "TAIEX" for f in market_pkg.facts)
    assert market_pkg.timezone == "Asia/Taipei"

    # 2. Security Grounding
    sec_pkg = await builder.build_security_grounding(sec_id, "req-2")
    assert sec_pkg.analysis_type == AnalysisType.SECURITY_SUMMARY
    assert "2330" in sec_pkg.target_identity
    assert any(f.key == "MA20" for f in sec_pkg.facts)


@pytest.mark.asyncio
async def test_ai_portfolio_consent_gating():
    session = FakeSession()
    user_id = uuid4()
    portfolio_id = uuid4()

    pf = PortfolioModel(
        id=portfolio_id, user_id=user_id, name="My Tech Stocks", base_currency="TWD"
    )
    session.objects[(PortfolioModel, portfolio_id)] = pf

    provider = FakeAIProvider()
    service = AIAnalysisService(session, provider)

    # 1. Consent is OFF by default -> must raise AI_PORTFOLIO_CONSENT_REQUIRED
    with pytest.raises(AppError) as exc_info:
        await service.analyze(
            analysis_type=AnalysisType.PORTFOLIO_SUMMARY,
            user_id=user_id,
            target_id=portfolio_id,
        )
    assert exc_info.value.code == "AI_PORTFOLIO_CONSENT_REQUIRED"

    # 2. Enable Consent
    await service.set_portfolio_consent(user_id, allow=True)
    assert await service.check_portfolio_consent(user_id) is True

    # 3. Analyze again -> succeeds with structured results
    res = await service.analyze(
        analysis_type=AnalysisType.PORTFOLIO_SUMMARY,
        user_id=user_id,
        target_id=portfolio_id,
    )
    assert res.provider == "FAKE"
    assert len(res.statements) > 0
    assert any(s.type == StatementType.FACT for s in res.statements)
    assert any(s.type == StatementType.INFERENCE for s in res.statements)


@pytest.mark.asyncio
async def test_unconfigured_ai_provider():
    session = FakeSession()
    provider = UnconfiguredAIProvider()
    assert provider.configured is False

    service = AIAnalysisService(session, provider)
    with pytest.raises(AppError) as exc_info:
        await service.analyze(analysis_type=AnalysisType.MARKET_SUMMARY)
    assert exc_info.value.code == "AI_PROVIDER_UNCONFIGURED"


@pytest.mark.asyncio
async def test_ai_redis_caching():
    session = FakeSession()
    provider = FakeAIProvider()
    redis = FakeRedis()
    service = AIAnalysisService(session, provider, redis_client=redis)

    # First call -> cache miss
    res1 = await service.analyze(analysis_type=AnalysisType.MARKET_SUMMARY)
    assert res1.cache_hit is False

    # Second call -> cache hit
    res2 = await service.analyze(analysis_type=AnalysisType.MARKET_SUMMARY)
    assert res2.cache_hit is True
    assert res2.summary == res1.summary


@pytest.mark.asyncio
async def test_push_token_lifecycle_and_dispatch():
    session = FakeSession()
    provider = FakePushProvider()
    redis = FakeRedis()
    service = PushNotificationService(session, provider, redis_client=redis)

    user_id = uuid4()
    device_pub = "device-pub-123"
    token = "fcm-registration-token-abc"

    # 1. Register Token
    await service.register_token(user_id, device_pub, token, platform="ANDROID")
    dev = (await session.scalars(select(UserDeviceModel))).first()
    assert dev is not None
    assert dev.push_token == token
    assert dev.revoked_at is None

    # 2. Dispatch Alert Event
    event_id = uuid4()
    results = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=event_id,
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="2330 TSMC reached target price 950.0",
    )
    assert len(results) == 1
    assert results[0].success is True
    assert len(provider.sent_messages) == 1

    # 3. Duplicate event ID -> dedup returns empty list
    dup_results = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=event_id,
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="2330 TSMC duplicate alert",
    )
    assert len(dup_results) == 0
    assert len(provider.sent_messages) == 1

    # 4. Unregister Token (e.g. on logout)
    await service.unregister_token(user_id, device_pub)
    assert dev.push_token is None

    # 5. Dispatch after unregister -> no messages sent
    event_id2 = uuid4()
    results2 = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=event_id2,
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="Alert after logout",
    )
    assert len(results2) == 0


def test_realtime_production_gate():
    # 1. Unconfigured
    res1 = RealtimeProductionGate.evaluate(None)
    assert res1["status"] == "UNCONFIGURED"
    assert res1["can_serve_live"] is False

    # 2. Delayed tier
    delayed_cap = ProviderCapabilities(
        provider_name="DelayedVendor",
        configured=True,
        source_type=SourceType.DELAYED,
        realtime_available=False,
        delay_seconds=900,
        license_status=LicenseStatus.AUTHORIZED,
        redistribution_allowed=True,
    )
    res2 = RealtimeProductionGate.evaluate(delayed_cap)
    assert res2["status"] == "DELAYED"
    assert res2["can_serve_live"] is False
    assert res2["delay_seconds"] == 900

    # 3. Unauthorized License
    unauth_cap = ProviderCapabilities(
        provider_name="MockVendor",
        configured=True,
        source_type=SourceType.BROKER,
        realtime_available=True,
        delay_seconds=0,
        license_status=LicenseStatus.UNAUTHORIZED,
        redistribution_allowed=True,
    )
    res3 = RealtimeProductionGate.evaluate(unauth_cap)
    assert res3["status"] == "UNAUTHORIZED"
    assert res3["can_serve_live"] is False

    # 4. Redistribution forbidden
    no_redist_cap = ProviderCapabilities(
        provider_name="PrivateFeed",
        configured=True,
        source_type=SourceType.EXCHANGE_DIRECT,
        realtime_available=True,
        delay_seconds=0,
        license_status=LicenseStatus.AUTHORIZED,
        redistribution_allowed=False,
    )
    res4 = RealtimeProductionGate.evaluate(no_redist_cap)
    assert res4["status"] == "UNAUTHORIZED_REDISTRIBUTION"
    assert res4["can_serve_live"] is False

    # 5. Production Authorized Realtime
    live_cap = ProviderCapabilities(
        provider_name="ExchangeDirect",
        configured=True,
        source_type=SourceType.EXCHANGE_DIRECT,
        realtime_available=True,
        delay_seconds=0,
        license_status=LicenseStatus.AUTHORIZED,
        redistribution_allowed=True,
    )
    res5 = RealtimeProductionGate.evaluate(live_cap)
    assert res5["status"] == "LIVE"
    assert res5["can_serve_live"] is True


@pytest.mark.asyncio
async def test_production_readiness_health():
    session = FakeSession()
    ai_provider = FakeAIProvider()
    push_provider = FakePushProvider()
    redis = FakeRedis()

    service = ProductionReadinessService(
        session=session,
        ai_provider=ai_provider,
        push_provider=push_provider,
        redis_client=redis,
    )

    report = await service.check_health()
    assert report["status"] == "HEALTHY"
    assert report["ready"] is True
    assert report["components"]["database"]["status"] == "UP"
    assert report["components"]["redis"]["status"] == "UP"
    assert report["components"]["ai_provider"]["status"] == "READY"
    assert report["components"]["push_provider"]["status"] == "READY"
    assert report["components"]["realtime_provider"]["status"] == "UNCONFIGURED"
