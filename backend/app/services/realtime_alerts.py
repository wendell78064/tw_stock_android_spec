import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from time import monotonic

from app.domain.alert import AlertEvaluationMode, AlertOccurrence, AlertRule, AlertRuleType
from app.domain.market_data import DataStatus
from app.domain.realtime import (
    DataStatus as RealtimeDataStatus,
)
from app.domain.realtime import (
    RealtimeEventKind,
    RealtimeQuote,
    TradingSession,
)

REALTIME_ALERT_CHANNEL = "realtime:alerts"
REALTIME_ALERT_STATE_TTL_SECONDS = 172800
TOUCH_TOLERANCE_PERCENT = Decimal("0.05")


@dataclass(frozen=True)
class RealtimeMaContext:
    period: int
    prior_sum: Decimal
    history_count: int

    def dynamic(self, price: Decimal) -> Decimal | None:
        if self.history_count != self.period - 1:
            return None
        return (self.prior_sum + price) / Decimal(self.period)


class RealtimeDailyMaService:
    def __init__(self, contexts: dict[tuple[str, int], RealtimeMaContext] | None = None):
        self.contexts = contexts or {}

    def value(self, security_id: str, period: int, price: Decimal) -> Decimal | None:
        context = self.contexts.get((security_id, period))
        return context.dynamic(price) if context else None


@dataclass
class RealtimeAlertState:
    trade_date: str
    last_price: str
    last_dynamic_ma: str | None
    last_relation: str | None
    last_sequence: int | None
    last_exchange_timestamp: str
    initialized: bool = True
    last_event_fingerprint: str | None = None


def _relation(price: Decimal, reference: Decimal | None) -> str | None:
    if reference is None:
        return None
    return "ABOVE" if price > reference else "BELOW" if price < reference else "TOUCH"


def evaluate_realtime_rule(
    rule: AlertRule,
    previous: RealtimeAlertState,
    quote: RealtimeQuote,
    previous_ma: Decimal | None,
    current_ma: Decimal | None,
) -> AlertOccurrence | None:
    old = Decimal(previous.last_price)
    current = quote.last_price
    kind = rule.rule_type
    triggered = False
    reference = rule.threshold_price
    label = kind.value
    if kind is AlertRuleType.PRICE_TARGET:
        triggered = old < reference <= current
    elif kind in {AlertRuleType.PRICE_STOP, AlertRuleType.PRICE_ADD}:
        triggered = old > reference >= current
    elif current_ma is None or previous_ma is None:
        return None
    elif kind is AlertRuleType.MA_CROSS_ABOVE:
        triggered = old <= previous_ma and current > current_ma
    elif kind is AlertRuleType.MA_CROSS_BELOW:
        triggered = old >= previous_ma and current < current_ma
    elif kind is AlertRuleType.MA_NEAR:
        old_distance = abs(old - previous_ma) / previous_ma * 100
        distance = abs(current - current_ma) / current_ma * 100
        triggered = old_distance > rule.threshold_percent >= distance
    elif kind is AlertRuleType.MA_TOUCH:
        old_distance = abs(old - previous_ma) / previous_ma * 100
        distance = abs(current - current_ma) / current_ma * 100
        crossed = (old < previous_ma and current > current_ma) or (
            old > previous_ma and current < current_ma
        )
        triggered = crossed or old_distance > TOUCH_TOLERANCE_PERCENT >= distance
    if not triggered or reference is None and current_ma is None:
        return None
    reference = reference if reference is not None else current_ma
    return AlertOccurrence(
        event_type=label,
        trigger_price=current,
        reference_value=reference,
        reference_type="PRICE"
        if kind.value.startswith("PRICE_")
        else f"DYNAMIC_MA{rule.ma_period}",
        message=f"{quote.code} 盤中 {label}，成交價 {current}，參考值 {reference}",
        data_status=DataStatus.LIVE,
        event_metadata={
            "evaluation_mode": "REALTIME",
            "exchange_timestamp": quote.exchange_timestamp.isoformat(),
            "provider": quote.provider,
            "sequence": quote.sequence,
            "trigger_price": str(current),
            "reference_value": str(reference),
            "reference_type": "PRICE"
            if kind.value.startswith("PRICE_")
            else f"DYNAMIC_MA{rule.ma_period}",
            "data_status": quote.data_status.value,
        },
    )


class RealtimeAlertEvaluationService:
    membership_refresh_interval_seconds = 60

    def __init__(self, redis, repository, ma_service: RealtimeDailyMaService | None = None):
        self.redis = redis
        self.repository = repository
        self.ma_service = ma_service or RealtimeDailyMaService()
        self.rules_by_security: dict[str, list[AlertRule]] = {}
        self.security_info: dict[str, tuple[str, str]] = {}
        self.provider_status = "UNCONFIGURED"
        self.last_quote_at: datetime | None = None
        self._last_refresh = monotonic()
        self.metrics = {
            name: 0
            for name in (
                "realtime_alert_quotes_processed",
                "realtime_alert_rules_evaluated",
                "realtime_alert_events_triggered",
                "realtime_alert_notifications_suppressed_cooldown",
                "realtime_alert_notifications_suppressed_daily_limit",
                "realtime_alert_replay_dropped",
                "realtime_alert_out_of_order_dropped",
                "realtime_alert_ma_context_cache_hits",
                "realtime_alert_ma_context_cache_misses",
                "realtime_alert_active_subscriptions",
            )
        }

    async def refresh(self) -> None:
        previous_pairs = {
            (str(rule.id), security_id)
            for security_id, rules in self.rules_by_security.items()
            for rule in rules
        }
        rules = [
            r
            for r in await self.repository.list_rules(True)
            if r.evaluation_mode is AlertEvaluationMode.REALTIME
        ]
        memberships = await self.repository.resolve_memberships(rules)
        security_ids = set().union(*memberships.values()) if memberships else set()
        contexts, info = await self.repository.realtime_ma_contexts(security_ids, rules)
        self.ma_service.contexts = contexts
        self.security_info = {str(key): (value[0], value[1]) for key, value in info.items()}
        self.rules_by_security = {}
        for rule in rules:
            for security_id in memberships.get(rule.id, set()):
                self.rules_by_security.setdefault(str(security_id), []).append(rule)
        current_pairs = {
            (str(rule.id), security_id)
            for security_id, rules in self.rules_by_security.items()
            for rule in rules
        }
        for rule_id, security_id in previous_pairs - current_pairs:
            await self.redis.delete(f"realtime:alert:state:{rule_id}:{security_id}")
        self.metrics["realtime_alert_active_subscriptions"] = len(self.rules_by_security)
        self._last_refresh = monotonic()

    def status(self) -> dict:
        return {
            "provider_status": self.provider_status,
            "realtime_available": self.provider_status in {"LIVE", "FAKE"},
            "authorized": self.provider_status == "LIVE",
            "active_rule_count": sum(map(len, self.rules_by_security.values())),
            "subscribed_security_count": len(self.rules_by_security),
            "last_quote_at": self.last_quote_at.isoformat() if self.last_quote_at else None,
        }

    async def accept(self, quote: RealtimeQuote) -> None:
        if monotonic() - self._last_refresh >= self.membership_refresh_interval_seconds:
            await self.refresh()
        self.metrics["realtime_alert_quotes_processed"] += 1
        self.last_quote_at = quote.exchange_timestamp
        if (
            quote.session is not TradingSession.REGULAR
            or quote.data_status is not RealtimeDataStatus.LIVE
        ):
            return
        for rule in self.rules_by_security.get(quote.security_id, []):
            await self._evaluate(rule, quote)

    async def _evaluate(self, rule: AlertRule, quote: RealtimeQuote) -> None:
        self.metrics["realtime_alert_rules_evaluated"] += 1
        key = f"realtime:alert:state:{rule.id}:{quote.security_id}"
        raw = await self.redis.get(key)
        state = RealtimeAlertState(**json.loads(raw)) if raw else None
        current_ma = (
            self.ma_service.value(quote.security_id, rule.ma_period, quote.last_price)
            if rule.ma_period
            else None
        )
        if rule.ma_period:
            metric = (
                "realtime_alert_ma_context_cache_hits"
                if current_ma is not None
                else "realtime_alert_ma_context_cache_misses"
            )
            self.metrics[metric] += 1
        trading_date = quote.exchange_timestamp.date().isoformat()
        baseline = (
            state is None
            or state.trade_date != trading_date
            or quote.event_kind is RealtimeEventKind.SNAPSHOT
        )
        if state and not baseline:
            timestamp = datetime.fromisoformat(state.last_exchange_timestamp)
            sequence_old = state.last_sequence
            if (
                quote.sequence is not None
                and sequence_old is not None
                and quote.sequence <= sequence_old
                or quote.exchange_timestamp <= timestamp
            ):
                self.metrics["realtime_alert_out_of_order_dropped"] += 1
                return
        previous_ma = (
            self.ma_service.value(quote.security_id, rule.ma_period, Decimal(state.last_price))
            if state and rule.ma_period
            else None
        )
        occurrence = (
            None
            if baseline
            else evaluate_realtime_rule(rule, state, quote, previous_ma, current_ma)
        )
        fingerprint = None
        if occurrence:
            identity = (
                quote.sequence
                if quote.sequence is not None
                else quote.exchange_timestamp.isoformat()
            )
            fingerprint = sha256(
                f"{rule.id}:{quote.security_id}:{occurrence.event_type}:{identity}".encode()
            ).hexdigest()
            if state.last_event_fingerprint == fingerprint or await self.repository.event_exists(
                fingerprint
            ):
                self.metrics["realtime_alert_replay_dropped"] += 1
            else:
                now = quote.exchange_timestamp
                cooldown = await self.repository.recent_event(
                    rule.id, quote.security_id, now - timedelta(minutes=rule.cooldown_minutes)
                )
                count = await self.repository.daily_notification_count(rule.id, now.date())
                eligible = not cooldown and count < rule.daily_limit
                if cooldown:
                    self.metrics["realtime_alert_notifications_suppressed_cooldown"] += 1
                elif count >= rule.daily_limit:
                    self.metrics["realtime_alert_notifications_suppressed_daily_limit"] += 1
                row = await self.repository.add_event(
                    rule, quote.security_id, now.date(), occurrence, fingerprint, eligible
                )
                await self.repository.flush()
                self.metrics["realtime_alert_events_triggered"] += 1
                await self.redis.publish(
                    REALTIME_ALERT_CHANNEL,
                    json.dumps(
                        {
                            "version": 1,
                            "type": "alert_event",
                            "event_id": str(row.id),
                            "fingerprint": fingerprint,
                            "notification_eligible": eligible,
                            "exchange_timestamp": quote.exchange_timestamp.isoformat(),
                            "provider": quote.provider,
                        }
                    ),
                )
        new_state = RealtimeAlertState(
            trading_date,
            str(quote.last_price),
            str(current_ma) if current_ma is not None else None,
            _relation(quote.last_price, current_ma),
            quote.sequence,
            quote.exchange_timestamp.isoformat(),
            last_event_fingerprint=fingerprint or (state.last_event_fingerprint if state else None),
        )
        await self.redis.set(
            key, json.dumps(asdict(new_state)), ex=REALTIME_ALERT_STATE_TTL_SECONDS
        )
