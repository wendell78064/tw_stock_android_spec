from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.domain.ai import (
    AnalysisType,
    StatementType,
)
from app.repositories.models import (
    MarketModel,
    PortfolioModel,
    SecurityModel,
)
from app.repositories.push_models import PushTokenModel
from app.services.ai_grounding import (
    AIAnalysisService,
    FakeAIProvider,
    GroundingBuilder,
    UnconfiguredAIProvider,
)
from app.services.production_readiness import (
    ProductionReadinessService,
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
        res = await self.scalars(statement)
        return res.first()

    async def scalars(self, stmt):
        entity = stmt.column_descriptions[0].get("entity") if stmt.column_descriptions else None
        if not entity:
            return SimpleNamespace(all=lambda: [], first=lambda: None)

        matched = []
        for (m, _), obj in self.objects.items():
            if m is not entity:
                continue
            matches = True

            def check_crit(target_obj, c):
                if hasattr(c, "left") and hasattr(c, "right"):
                    left = getattr(c, "left", None)
                    right = getattr(c, "right", None)
                    col_name = getattr(left, "name", None)
                    val = getattr(right, "value", None)
                    modifier = getattr(c, "modifier", None)

                    if modifier is not None and str(modifier) == "is_true":
                        val_col = getattr(target_obj, col_name, None)
                        return bool(val_col)

                    if col_name and hasattr(target_obj, col_name):
                        obj_val = getattr(target_obj, col_name)
                        op_name = getattr(getattr(c, "operator", None), "__name__", "")
                        right_type = getattr(getattr(c, "right", None), "__class__", None)
                        right_name = getattr(right_type, "__name__", "")
                        if right_name == "True_":
                            return bool(obj_val) is True
                        if right_name == "False_":
                            return bool(obj_val) is False
                        if "lt" in op_name:
                            return obj_val is not None and val is not None and obj_val < val
                        if isinstance(val, list | tuple | set):
                            return obj_val in val
                        if val is not None:
                            return obj_val == val
                        if modifier is not None and "is_not" in str(modifier):
                            return obj_val is not None
                    return True

                if hasattr(c, "clauses"):
                    op_name = getattr(getattr(c, "operator", None), "__name__", "")
                    if "or" in op_name or getattr(c, "__class__", None).__name__ == "Or":
                        return any(check_crit(target_obj, sub) for sub in c.clauses)
                    else:
                        return all(check_crit(target_obj, sub) for sub in c.clauses)
                return True

            for crit in getattr(stmt, "_where_criteria", ()):
                if not check_crit(obj, crit):
                    matches = False
                    break
            if matches:
                matched.append(obj)
        limit = getattr(stmt, "_limit", None)
        if limit is not None:
            matched = matched[:limit]
        return SimpleNamespace(all=lambda: matched, first=lambda: matched[0] if matched else None)

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
@pytest.mark.asyncio
async def test_push_token_lifecycle_and_dispatch():
    session = FakeSession()
    provider = FakePushProvider()
    redis = FakeRedis()
    service = PushNotificationService(session, provider, redis_client=redis)

    user_id = uuid4()
    device_pub = "device-pub-123"
    token = "fcm-registration-token-abc"

    # Add owned device
    from app.repositories.models import UserDeviceModel
    session.add(UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    ))

    # 1. Register Token
    await service.register_token(user_id, device_pub, token, platform="ANDROID")
    tok = (await session.scalars(select(PushTokenModel))).first()
    assert tok is not None
    assert tok.token == token
    assert tok.active is True

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
    assert tok.active is False

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


@pytest.mark.asyncio
async def test_production_readiness_with_unconfigured_providers():
    session = FakeSession()
    ai_provider = UnconfiguredAIProvider()
    from app.services.push_notifications import UnconfiguredPushProvider
    push_provider = UnconfiguredPushProvider()

    service = ProductionReadinessService(
        session=session,
        ai_provider=ai_provider,
        push_provider=push_provider,
    )

    report = await service.check_health()
    assert report["components"]["ai_provider"]["status"] == "UNCONFIGURED"
    assert report["components"]["ai_provider"]["configured"] is False
    assert report["components"]["push_provider"]["status"] == "UNCONFIGURED"
    assert report["components"]["push_provider"]["configured"] is False


@pytest.mark.asyncio
async def test_unconfigured_ai_provider_fails_closed():
    provider = UnconfiguredAIProvider()
    assert provider.configured is False
    assert (await provider.health())["status"] == "UNCONFIGURED"

    session = FakeSession()
    service = AIAnalysisService(session, provider)
    with pytest.raises(AppError) as exc:
        await service.analyze(analysis_type=AnalysisType.MARKET_SUMMARY)
    assert exc.value.code == "AI_PROVIDER_UNCONFIGURED"


@pytest.mark.asyncio
async def test_unconfigured_push_provider_fails_closed():
    from app.domain.push import PushNotificationPayload
    from app.services.push_notifications import UnconfiguredPushProvider

    provider = UnconfiguredPushProvider()
    assert provider.configured is False
    assert (await provider.health())["status"] == "UNCONFIGURED"

    res = await provider.send(
        "dummy-token",
        PushNotificationPayload(
            event_id="e1",
            alert_type="PRICE_BREAKTHROUGH",
            security_code="2330",
            title="Test",
            body="Body",
        ),
    )
    assert res.success is False
    assert res.provider == "UNCONFIGURED"
    assert res.error == "PUSH_PROVIDER_UNCONFIGURED"

