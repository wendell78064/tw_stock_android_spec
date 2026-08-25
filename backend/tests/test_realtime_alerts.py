from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.settings import Settings
from app.domain.alert import AlertEvaluationMode, AlertRuleType, AlertScopeType
from app.domain.realtime import (
    DataStatus,
    LicenseStatus,
    ProviderCapabilities,
    RealtimeEventKind,
    RealtimeQuote,
    RealtimeQuoteType,
    TradingSession,
)
from app.services.realtime_alerts import (
    P1_ALERT_OWNER,
    RealtimeAlertEvaluationService,
    RealtimeAlertSubscriptionPolicy,
    RealtimeDailyMaService,
    RealtimeMaContext,
)
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_capacity import RealtimeCapacityError
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_provider_manager import RealtimeProviderManager
from tests.test_alerts import rule

D = Decimal


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.published = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def publish(self, channel, value):
        self.published.append((channel, value))

    async def delete(self, key):
        self.values.pop(key, None)


class RealtimeRepo:
    def __init__(self, rules):
        self.rules = rules
        self.events = []
        self.fingerprints = set()
        self.cooldown = False
        self.count = 0

    async def event_exists(self, fingerprint):
        return fingerprint in self.fingerprints

    async def recent_event(self, *args):
        return self.cooldown

    async def daily_notification_count(self, *args):
        return self.count

    async def add_event(
        self, alert_rule, security_id, trade_date, occurrence, fingerprint, eligible
    ):
        self.fingerprints.add(fingerprint)
        self.events.append((alert_rule, occurrence, eligible))
        return SimpleNamespace(id=uuid4())

    async def flush(self):
        return None


class MembershipRepo:
    def __init__(self, rules, memberships, info):
        self.rules = rules
        self.memberships = memberships
        self.info = info

    async def list_rules(self, enabled=None):
        if enabled is None:
            return self.rules
        return [item for item in self.rules if item.enabled is enabled]

    async def resolve_memberships(self, rules):
        return {item.id: self.memberships.get(item.id, set()) for item in rules}

    async def realtime_ma_contexts(self, security_ids, rules):
        return {}, {key: self.info[key] for key in security_ids}


def realtime_rule(kind, **kwargs):
    return replace(rule(kind, **kwargs), evaluation_mode=AlertEvaluationMode.REALTIME)


def quote(
    security_id,
    price,
    sequence,
    *,
    kind=RealtimeEventKind.UPDATE,
    day=13,
    status=DataStatus.LIVE,
    session=TradingSession.REGULAR,
):
    timestamp = datetime(2026, 8, day, 1, tzinfo=UTC) + timedelta(seconds=sequence)
    return RealtimeQuote(
        security_id=str(security_id),
        market_id="TWSE",
        code="1234",
        exchange_timestamp=timestamp,
        received_at=timestamp,
        last_price=D(price),
        sequence=sequence,
        event_kind=kind,
        data_status=status,
        session=session,
        provider="FAKE_REALTIME_PROVIDER",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "first", "second"),
    [
        (AlertRuleType.PRICE_TARGET, "9", "11"),
        (AlertRuleType.PRICE_STOP, "11", "9"),
        (AlertRuleType.PRICE_ADD, "11", "9"),
    ],
)
async def test_price_snapshot_baseline_and_cross(kind, first, second):
    alert_rule = realtime_rule(kind, price=D("10"))
    repo = RealtimeRepo([alert_rule])
    redis = FakeRedis()
    service = RealtimeAlertEvaluationService(redis, repo)
    service.rules_by_security = {str(alert_rule.security_id): [alert_rule]}
    await service.accept(quote(alert_rule.security_id, first, 1, kind=RealtimeEventKind.SNAPSHOT))
    assert not repo.events
    await service.accept(quote(alert_rule.security_id, second, 2))
    assert len(repo.events) == 1


@pytest.mark.asyncio
async def test_reconnect_replay_order_day_and_status_are_safe():
    alert_rule = realtime_rule(AlertRuleType.PRICE_TARGET, price=D("10"))
    repo = RealtimeRepo([alert_rule])
    service = RealtimeAlertEvaluationService(FakeRedis(), repo)
    service.rules_by_security = {str(alert_rule.security_id): [alert_rule]}
    await service.accept(quote(alert_rule.security_id, "9", 1))
    await service.accept(quote(alert_rule.security_id, "11", 2, kind=RealtimeEventKind.SNAPSHOT))
    await service.accept(quote(alert_rule.security_id, "12", 1))
    await service.accept(quote(alert_rule.security_id, "9", 3, status=DataStatus.STALE))
    await service.accept(quote(alert_rule.security_id, "11", 1, day=14))
    assert not repo.events
    await service.accept(quote(alert_rule.security_id, "9", 2, day=14))
    await service.accept(quote(alert_rule.security_id, "11", 3, day=14))
    assert len(repo.events) == 1


@pytest.mark.asyncio
async def test_dynamic_ma_cross_near_touch_and_history_coverage():
    security_id = str(uuid4())
    context = RealtimeMaContext(5, D("40"), 4)
    ma = RealtimeDailyMaService({(security_id, 5): context})
    assert ma.value(security_id, 5, D("10")) == D("10")
    assert RealtimeMaContext(5, D("30"), 3).dynamic(D("10")) is None
    alert_rule = replace(realtime_rule(AlertRuleType.MA_CROSS_ABOVE, ma=5), security_id=uuid4())
    security_id = str(alert_rule.security_id)
    ma.contexts[(security_id, 5)] = context
    repo = RealtimeRepo([alert_rule])
    service = RealtimeAlertEvaluationService(FakeRedis(), repo, ma)
    service.rules_by_security = {security_id: [alert_rule]}
    await service.accept(quote(security_id, "9", 1))
    await service.accept(quote(security_id, "11", 2))
    assert repo.events[0][1].reference_value == D("10.2")
    assert RealtimeMaContext(240, D("2390"), 238).dynamic(D("10")) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kind", "first", "second", "pct"),
    [
        (AlertRuleType.MA_CROSS_BELOW, "11", "9", None),
        (AlertRuleType.MA_NEAR, "11", "10.01", D("1")),
        (AlertRuleType.MA_TOUCH, "9.9", "10", None),
    ],
)
async def test_dynamic_ma_near_touch_and_cross_below(kind, first, second, pct):
    alert_rule = realtime_rule(kind, ma=5, pct=pct)
    security_id = str(alert_rule.security_id)
    repo = RealtimeRepo([alert_rule])
    service = RealtimeAlertEvaluationService(
        FakeRedis(),
        repo,
        RealtimeDailyMaService({(security_id, 5): RealtimeMaContext(5, D("40"), 4)}),
    )
    service.rules_by_security = {security_id: [alert_rule]}
    await service.accept(quote(security_id, first, 1))
    await service.accept(quote(security_id, second, 2))
    assert len(repo.events) == 1


@pytest.mark.asyncio
async def test_cooldown_daily_limit_and_second_crossing_audit():
    alert_rule = realtime_rule(AlertRuleType.PRICE_TARGET, price=D("10"))
    repo = RealtimeRepo([alert_rule])
    service = RealtimeAlertEvaluationService(FakeRedis(), repo)
    service.rules_by_security = {str(alert_rule.security_id): [alert_rule]}
    await service.accept(quote(alert_rule.security_id, "9", 1))
    await service.accept(quote(alert_rule.security_id, "11", 2))
    await service.accept(quote(alert_rule.security_id, "9", 3))
    repo.cooldown = True
    await service.accept(quote(alert_rule.security_id, "11", 4))
    assert len(repo.events) == 2 and repo.events[0][2] and not repo.events[1][2]


@pytest.mark.asyncio
async def test_2000_rule_evaluations_performance_smoke():
    rules = [realtime_rule(AlertRuleType.PRICE_TARGET, price=D("10")) for _ in range(20)]
    repo = RealtimeRepo(rules)
    service = RealtimeAlertEvaluationService(FakeRedis(), repo)
    for security_index in range(100):
        security_id = str(security_index)
        service.rules_by_security[security_id] = rules
        await service.accept(quote(security_id, "9", 1))
    started = perf_counter()
    for security_index in range(100):
        await service.accept(quote(str(security_index), "9.5", 2))
    elapsed_ms = (perf_counter() - started) * 1000
    print(f"realtime-alert: 100 securities / 2000 rules = {elapsed_ms:.3f}ms burst")
    assert service.metrics["realtime_alert_rules_evaluated"] == 4000
    assert elapsed_ms / 100 < 10


@pytest.mark.asyncio
async def test_alert_websocket_protocol_v1_channel():
    redis = FakeRedis()
    hub = RealtimeQuoteHub(redis, RealtimeCacheService(redis))
    websocket = AsyncMock()
    session = await hub.register_connection(websocket)
    await hub.handle_subscribe(session, [], ["alert"])
    hub._route_global("alert", "alert_event", {"event_id": "event-1"})
    await __import__("asyncio").sleep(0)
    payload = websocket.send_json.call_args.args[0]
    assert payload["version"] == 1 and payload["type"] == "alert_event"


@pytest.mark.asyncio
async def test_p1_membership_uses_canonical_enabled_realtime_scope_expansion():
    security_id, portfolio_security, watchlist_security = uuid4(), uuid4(), uuid4()
    security_rule = replace(
        realtime_rule(AlertRuleType.PRICE_TARGET, price=D("10")),
        security_id=security_id,
    )
    portfolio_rule = replace(
        realtime_rule(AlertRuleType.MA_TOUCH, ma=5),
        scope_type=AlertScopeType.PORTFOLIO,
        security_id=None,
        portfolio_id=uuid4(),
    )
    watchlist_rule = replace(
        realtime_rule(AlertRuleType.PRICE_STOP, price=D("10")),
        scope_type=AlertScopeType.WATCHLIST,
        security_id=None,
        watchlist_id=uuid4(),
    )
    duplicate_rule = replace(security_rule, id=uuid4())
    disabled_rule = replace(security_rule, id=uuid4(), enabled=False)
    daily_rule = replace(security_rule, id=uuid4(), evaluation_mode=AlertEvaluationMode.EOD)
    rules = [
        security_rule,
        portfolio_rule,
        watchlist_rule,
        duplicate_rule,
        disabled_rule,
        daily_rule,
    ]
    memberships = {
        security_rule.id: {security_id},
        portfolio_rule.id: {portfolio_security},
        watchlist_rule.id: {watchlist_security},
        duplicate_rule.id: {security_id},
    }
    info = {
        security_id: ("2330", "", "TWSE"),
        portfolio_security: ("6488", "", "TPEX"),
        watchlist_security: ("2454", "", "TWSE"),
    }
    service = RealtimeAlertEvaluationService(
        FakeRedis(), MembershipRepo(rules, memberships, info)
    )

    await service.refresh()

    assert service.realtime_security_keys() == {
        "TWSE:2330",
        "TPEX:6488",
        "TWSE:2454",
    }
    assert len(service.rules_by_security[str(security_id)]) == 2


@pytest.mark.asyncio
async def test_p1_policy_diffs_tick_membership_without_churn_or_bidask():
    service = AsyncMock()
    manager = AsyncMock()
    policy = RealtimeAlertSubscriptionPolicy(service, manager)

    await policy.reconcile({"TWSE:2330", "TPEX:6488"})
    await policy.reconcile({"TWSE:2330", "TPEX:6488"})
    await policy.reconcile({"TWSE:2330", "TWSE:2454"})

    acquired = [call.args for call in manager.acquire_subscription.await_args_list]
    released = [call.args for call in manager.release_subscription.await_args_list]
    assert acquired == [
        (P1_ALERT_OWNER, "TPEX:6488", RealtimeQuoteType.TICK),
        (P1_ALERT_OWNER, "TWSE:2330", RealtimeQuoteType.TICK),
        (P1_ALERT_OWNER, "TWSE:2454", RealtimeQuoteType.TICK),
    ]
    assert released == [(P1_ALERT_OWNER, "TPEX:6488", RealtimeQuoteType.TICK)]


@pytest.mark.asyncio
async def test_p0_p1_p2_share_tick_while_bidask_remains_p2_only():
    provider = AsyncMock()
    provider.get_capabilities.return_value = ProviderCapabilities(
        provider_name="TEST",
        source_type="WEBSOCKET",
        configured=True,
        realtime_available=True,
        license_status=LicenseStatus.AUTHORIZED,
    )
    manager = RealtimeProviderManager(provider, AsyncMock(), AsyncMock())
    security = "TWSE:2330"

    await manager.acquire_subscription("policy:p0_portfolio", security, RealtimeQuoteType.TICK)
    await manager.acquire_subscription(P1_ALERT_OWNER, security, RealtimeQuoteType.TICK)
    await manager.acquire_subscription("policy:p2_current_view", security, RealtimeQuoteType.TICK)
    await manager.acquire_subscription(
        "policy:p2_current_view", security, RealtimeQuoteType.BID_ASK
    )
    assert provider.acquire_subscription.await_count == 2

    await manager.release_subscription("policy:p2_current_view", security, RealtimeQuoteType.TICK)
    await manager.release_subscription(
        "policy:p2_current_view", security, RealtimeQuoteType.BID_ASK
    )
    assert provider.release_subscription.await_count == 1
    await manager.release_subscription("policy:p0_portfolio", security, RealtimeQuoteType.TICK)
    assert provider.release_subscription.await_count == 1
    await manager.release_subscription(P1_ALERT_OWNER, security, RealtimeQuoteType.TICK)
    assert provider.release_subscription.await_count == 2


@pytest.mark.asyncio
async def test_p1_refresh_restores_only_current_membership_and_shutdown_releases_it():
    security_id = uuid4()
    alert_rule = replace(
        realtime_rule(AlertRuleType.PRICE_TARGET, price=D("10")), security_id=security_id
    )
    repository = MembershipRepo(
        [alert_rule], {alert_rule.id: {security_id}}, {security_id: ("2330", "", "TWSE")}
    )
    service = RealtimeAlertEvaluationService(FakeRedis(), repository)
    manager = AsyncMock()
    policy = RealtimeAlertSubscriptionPolicy(service, manager, refresh_interval_seconds=3600)

    await policy.start()
    repository.rules = []
    await service.refresh()
    await policy.stop()

    manager.acquire_subscription.assert_awaited_once_with(
        P1_ALERT_OWNER, "TWSE:2330", RealtimeQuoteType.TICK
    )
    manager.release_subscription.assert_awaited_once_with(
        P1_ALERT_OWNER, "TWSE:2330", RealtimeQuoteType.TICK
    )
    assert policy.membership == set()


def test_p1_feature_gate_defaults_disabled():
    assert Settings().p1_alert_realtime_enabled is False


@pytest.mark.asyncio
async def test_p1_capacity_rejection_reports_partial_without_disturbing_existing_owner():
    service = SimpleNamespace(
        subscription_status="DISABLED", subscription_rejected_count=0
    )
    manager = AsyncMock()
    manager.acquire_subscription.side_effect = [None, RealtimeCapacityError("full")]
    policy = RealtimeAlertSubscriptionPolicy(service, manager)

    await policy.reconcile({"TWSE:2330", "TWSE:2454"})

    assert policy.membership == {"TWSE:2330"}
    assert policy.rejected_membership == {"TWSE:2454"}
    assert service.subscription_status == "PARTIAL"
    assert service.subscription_rejected_count == 1
    manager.release_subscription.assert_not_awaited()
