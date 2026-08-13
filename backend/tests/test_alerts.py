from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.alerts import router
from app.core.dependencies import alert_repository
from app.core.errors import AppError, app_error_handler
from app.domain.alert import AlertRule, AlertRuleType, AlertScopeType, MarketPoint, validate_rule
from app.domain.market_data import DataStatus
from app.services.alert_evaluators import evaluate
from app.services.alerts import AlertEvaluationService

D = Decimal
SID = uuid4()


def rule(kind, ma=None, price=None, pct=None, days=None):
    now = datetime.now(UTC)
    return AlertRule(
        uuid4(),
        kind.value,
        kind,
        AlertScopeType.SECURITY,
        SID,
        None,
        None,
        ma,
        price,
        pct,
        days,
        True,
        1440,
        5,
        now,
        now,
    )


def point(day, close, ma=None, low=None, high=None, status=DataStatus.FINAL):
    return MarketPoint(SID, date(2026, 8, day), close, high, low, close, {20: ma}, status)


@pytest.mark.parametrize(
    ("kind", "previous", "current", "threshold"),
    [
        (AlertRuleType.PRICE_TARGET, D("9"), D("10"), D("10")),
        (AlertRuleType.PRICE_STOP, D("11"), D("10"), D("10")),
        (AlertRuleType.PRICE_ADD, D("11"), D("10"), D("10")),
    ],
)
def test_price_crosses(kind, previous, current, threshold):
    assert evaluate(rule(kind, price=threshold), [point(10, previous), point(11, current)], "1234")


def test_price_no_cross_and_missing_previous():
    r = rule(AlertRuleType.PRICE_TARGET, price=D("10"))
    assert evaluate(r, [point(10, D("10")), point(11, D("11"))], "1234") is None
    assert evaluate(r, [point(11, D("11"))], "1234") is None


@pytest.mark.parametrize(
    ("kind", "history"),
    [
        (AlertRuleType.MA_NEAR, [point(11, D("10.05"), D("10"))]),
        (AlertRuleType.MA_TOUCH, [point(11, D("11"), D("10"), D("9"), D("12"))]),
        (AlertRuleType.MA_CROSS_ABOVE, [point(10, D("9"), D("10")), point(11, D("11"), D("10"))]),
        (AlertRuleType.MA_CROSS_BELOW, [point(10, D("11"), D("10")), point(11, D("9"), D("10"))]),
        (AlertRuleType.MA_CLOSE_ABOVE, [point(11, D("11"), D("10"))]),
        (AlertRuleType.MA_CLOSE_BELOW, [point(11, D("9"), D("10"))]),
    ],
)
def test_ma_conditions(kind, history):
    assert evaluate(
        rule(kind, ma=20, pct=D("1") if kind is AlertRuleType.MA_NEAR else None), history, "1234"
    )


@pytest.mark.parametrize(
    ("kind", "close"),
    [(AlertRuleType.MA_CONSECUTIVE_ABOVE, D("11")), (AlertRuleType.MA_CONSECUTIVE_BELOW, D("9"))],
)
def test_consecutive(kind, close):
    assert evaluate(
        rule(kind, ma=20, days=3),
        [point(7, close, D("10")), point(10, close, D("10")), point(11, close, D("10"))],
        "1234",
    )


def test_missing_ma_and_unavailable_do_not_trigger():
    r = rule(AlertRuleType.MA_CLOSE_ABOVE, ma=20)
    assert evaluate(r, [point(11, D("11"), None)], "1234") is None
    assert evaluate(r, [point(11, D("11"), D("10"), status=DataStatus.UNAVAILABLE)], "1234") is None


def test_stale_is_retained():
    assert (
        evaluate(
            rule(AlertRuleType.MA_CLOSE_ABOVE, ma=20),
            [point(11, D("11"), D("10"), status=DataStatus.STALE)],
            "1234",
        ).data_status
        is DataStatus.STALE
    )


def test_partial_is_retained_when_required_fields_are_complete():
    occurrence = evaluate(
        rule(AlertRuleType.MA_CLOSE_ABOVE, ma=20),
        [point(11, D("11"), D("10"), status=DataStatus.PARTIAL)],
        "1234",
    )
    assert occurrence is not None and occurrence.data_status is DataStatus.PARTIAL


def test_unavailable_previous_required_point_does_not_trigger():
    assert (
        evaluate(
            rule(AlertRuleType.PRICE_TARGET, price=D("10")),
            [point(10, D("9"), status=DataStatus.UNAVAILABLE), point(11, D("11"))],
            "1234",
        )
        is None
    )


def test_validation():
    validate_rule(
        AlertRuleType.MA_NEAR,
        AlertScopeType.SECURITY,
        SID,
        None,
        None,
        20,
        None,
        D("1"),
        None,
        1440,
        5,
    )
    with pytest.raises(ValueError):
        validate_rule(
            AlertRuleType.MA_NEAR,
            AlertScopeType.SECURITY,
            SID,
            None,
            None,
            20,
            None,
            D("21"),
            None,
            1440,
            5,
        )


class MemoryEngine:
    def __init__(self):
        self.rule = rule(AlertRuleType.PRICE_TARGET, price=D("10"))
        self.fingerprints, self.events, self.runs, self.members = set(), [], [], {SID}
        self.disabled = False

    async def start_run(self, target):
        self.runs.append([target])
        return uuid4()

    async def list_rules(self, enabled=None):
        return [] if self.disabled else [self.rule]

    async def resolve_memberships(self, rules):
        return {self.rule.id: set(self.members)}

    async def market_history(self, ids, target, days):
        return (
            {SID: [point(10, D("9")), point(11, D("11"))]} if ids else {},
            {SID: ("1234", "測試股票", "TWSE")},
        )

    async def event_exists(self, value):
        return value in self.fingerprints

    async def event_state(self, rule_ids, target, since):
        return (
            set(self.fingerprints),
            {},
            {self.rule.id: sum(event[-1] for event in self.events)},
        )

    async def recent_event(self, *args):
        return False

    async def daily_notification_count(self, *args):
        return sum(event[-1] for event in self.events)

    async def add_event(self, r, s, d, o, f, eligible):
        self.fingerprints.add(f)
        self.events.append((r, s, d, o, f, eligible))

    async def flush(self):
        pass

    async def finish_run(self, *values):
        self.runs[-1].extend(values[1:])


@pytest.mark.asyncio
async def test_engine_dedup_audit_disabled_and_dynamic_membership():
    repo = MemoryEngine()
    engine = AlertEvaluationService(repo)
    first = await engine.evaluate(date(2026, 8, 11))
    second = await engine.evaluate(date(2026, 8, 11))
    assert first["events_created"] == 1 and second["events_created"] == 0 and len(repo.runs) == 2
    repo.disabled = True
    assert (await engine.evaluate(date(2026, 8, 11)))["rules_evaluated"] == 0
    repo.disabled = False
    repo.members = set()
    assert (await engine.evaluate(date(2026, 8, 11)))["securities_evaluated"] == 0


@pytest.mark.asyncio
async def test_daily_limit_keeps_history_without_delivery():
    repo = MemoryEngine()
    repo.rule = AlertRule(**{**repo.rule.__dict__, "daily_limit": 1})
    repo.events.append((None, None, None, None, None, True))
    await AlertEvaluationService(repo).evaluate(date(2026, 8, 11))
    assert len(repo.events) == 2 and repo.events[-1][-1] is False


class ApiRepository:
    def __init__(self):
        self.rules = {}
        self.read_all = False

    async def list_rules(self, enabled=None):
        values = list(self.rules.values())
        return values if enabled is None else [item for item in values if item.enabled == enabled]

    async def get_rule(self, rule_id):
        return self.rules.get(rule_id)

    async def save_rule(self, values, rule_id=None):
        now = datetime.now(UTC)
        current = self.rules.get(rule_id)
        saved = AlertRule(
            rule_id or uuid4(),
            values["name"],
            AlertRuleType(values["rule_type"]),
            AlertScopeType(values["scope_type"]),
            values["security_id"],
            values["portfolio_id"],
            values["watchlist_id"],
            values["ma_period"],
            values["threshold_price"],
            values["threshold_percent"],
            values["consecutive_days"],
            values["enabled"],
            values["cooldown_minutes"],
            values["daily_limit"],
            current.created_at if current else now,
            now,
        )
        self.rules[saved.id] = saved
        return saved

    async def set_enabled(self, rule_id, enabled):
        self.rules[rule_id] = replace(self.rules[rule_id], enabled=enabled)

    async def delete_rule(self, rule_id):
        self.rules.pop(rule_id)

    async def list_events(self, *args, **kwargs):
        return []

    async def mark_all_read(self):
        self.read_all = True


def test_rule_crud_toggle_and_notification_routes():
    repository = ApiRepository()
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(router, prefix="/v1")
    app.dependency_overrides[alert_repository] = lambda: repository
    client = TestClient(app)
    payload = {
        "name": "台積電目標價",
        "rule_type": "PRICE_TARGET",
        "scope_type": "SECURITY",
        "security_id": str(SID),
        "threshold_price": "1000",
    }
    created = client.post("/v1/alerts/rules", json=payload)
    assert created.status_code == 201
    rule_id = created.json()["data"]["id"]
    assert len(client.get("/v1/alerts/rules").json()["data"]) == 1
    assert client.post(f"/v1/alerts/rules/{rule_id}/disable").json()["data"]["enabled"] is False
    assert client.get("/v1/notifications").status_code == 200
    assert client.post("/v1/notifications/read-all").status_code == 200
    assert repository.read_all
    assert client.delete(f"/v1/alerts/rules/{rule_id}").status_code == 204
    invalid = {
        **payload,
        "rule_type": "MA_CONSECUTIVE_ABOVE",
        "threshold_price": None,
        "ma_period": 20,
        "consecutive_days": 3,
        "evaluation_mode": "REALTIME",
    }
    assert client.post("/v1/alerts/rules", json=invalid).status_code == 422


class PerformanceEngine(MemoryEngine):
    def __init__(self):
        super().__init__()
        self.rules = [replace(self.rule, id=uuid4(), name=f"rule-{index}") for index in range(20)]
        self.security_ids = {uuid4() for _ in range(50)}
        self.calls = {"membership": 0, "history": 0, "state": 0}

    async def list_rules(self, enabled=None):
        return self.rules

    async def resolve_memberships(self, rules):
        self.calls["membership"] += 1
        return {item.id: set(self.security_ids) for item in rules}

    async def market_history(self, ids, target, days):
        self.calls["history"] += 1
        return (
            {
                security_id: [
                    replace(point(10, D("9")), security_id=security_id),
                    replace(point(11, D("11")), security_id=security_id),
                ]
                for security_id in ids
            },
            {
                security_id: (str(index), "測試股票", "TWSE")
                for index, security_id in enumerate(ids)
            },
        )

    async def event_state(self, rule_ids, target, since):
        self.calls["state"] += 1
        return set(), {}, {}


@pytest.mark.asyncio
async def test_50_securities_by_20_rules_performance():
    repository = PerformanceEngine()
    started = perf_counter()
    result = await AlertEvaluationService(repository).evaluate(date(2026, 8, 11))
    elapsed_ms = (perf_counter() - started) * 1000
    assert result["events_created"] == 1000
    assert repository.calls == {"membership": 1, "history": 1, "state": 1}
    assert elapsed_ms < 500
