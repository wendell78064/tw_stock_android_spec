from datetime import UTC, date, datetime, timedelta
from hashlib import sha256

from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.core.errors import AppError
from app.domain.alert import validate_rule
from app.services.alert_evaluators import evaluate


class AlertRuleService:
    def __init__(self, repository):
        self.repository = repository

    async def save(self, values, rule_id=None):
        try:
            validate_rule(
                **{
                    key: values[key]
                    for key in (
                        "rule_type",
                        "scope_type",
                        "security_id",
                        "portfolio_id",
                        "watchlist_id",
                        "ma_period",
                        "threshold_price",
                        "threshold_percent",
                        "consecutive_days",
                        "cooldown_minutes",
                        "daily_limit",
                    )
                }
            )
        except ValueError as exc:
            raise AppError("ALERT_RULE_INVALID", str(exc), 422) from exc
        if rule_id and await self.repository.get_rule(rule_id) is None:
            raise AppError("ALERT_RULE_NOT_FOUND", "找不到提醒規則", 404)
        values = {
            **values,
            "rule_type": values["rule_type"].value,
            "scope_type": values["scope_type"].value,
        }
        return await self.repository.save_rule(values, rule_id)

    async def require(self, rule_id):
        row = await self.repository.get_rule(rule_id)
        if row is None:
            raise AppError("ALERT_RULE_NOT_FOUND", "找不到提醒規則", 404)
        return row


class AlertEvaluationService:
    def __init__(self, repository, calendar=None):
        self.repository = repository
        self.calendar = calendar or WeekendOnlyCalendar()

    async def evaluate(self, target_date: date | None = None):
        target = target_date or self._latest_completed(datetime.now(UTC).date())
        run_id = await self.repository.start_run(target)
        rules = await self.repository.list_rules(True)
        membership = await self.repository.resolve_memberships(rules)
        security_ids = set().union(*membership.values()) if membership else set()
        max_days = max([rule.consecutive_days or 2 for rule in rules], default=2)
        history, info = await self.repository.market_history(security_ids, target, max_days)
        since = datetime.now(UTC) - timedelta(
            minutes=max([rule.cooldown_minutes for rule in rules], default=0)
        )
        fingerprints, latest_events, counts = await self.repository.event_state(
            [rule.id for rule in rules], target, since
        )
        created = errors = 0
        for rule in rules:
            for security_id in membership.get(rule.id, set()):
                try:
                    points = [
                        point
                        for point in history.get(security_id, [])
                        if self.calendar.is_trading_day(point.trade_date)
                        and point.trade_date <= target
                    ]
                    occurrence = evaluate(
                        rule, points, info.get(security_id, (str(security_id), "", ""))[0]
                    )
                    if occurrence is None:
                        continue
                    fingerprint = sha256(
                        f"{rule.id}:{security_id}:{target}:{occurrence.event_type}".encode()
                    ).hexdigest()
                    if fingerprint in fingerprints:
                        continue
                    previous_event = latest_events.get((rule.id, security_id))
                    cooldown = previous_event is not None and previous_event >= datetime.now(
                        UTC
                    ) - timedelta(minutes=rule.cooldown_minutes)
                    count = counts.get(rule.id, 0)
                    await self.repository.add_event(
                        rule,
                        security_id,
                        target,
                        occurrence,
                        fingerprint,
                        not cooldown and count < rule.daily_limit,
                    )
                    fingerprints.add(fingerprint)
                    latest_events[(rule.id, security_id)] = datetime.now(UTC)
                    if not cooldown and count < rule.daily_limit:
                        counts[rule.id] = count + 1
                    created += 1
                except Exception:
                    errors += 1
        await self.repository.flush()
        await self.repository.finish_run(run_id, len(rules), len(security_ids), created, errors)
        return {
            "run_id": str(run_id),
            "target_trade_date": target.isoformat(),
            "rules_evaluated": len(rules),
            "securities_evaluated": len(security_ids),
            "events_created": created,
            "errors": errors,
            "status": "SUCCESS" if errors == 0 else "PARTIAL",
        }

    def _latest_completed(self, value):
        candidate = value
        while not self.calendar.is_trading_day(candidate):
            candidate = self.calendar.previous_trading_day(candidate)
        return candidate


class NotificationDeliveryProvider:
    status = "UNCONFIGURED"
