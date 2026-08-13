# ruff: noqa: E501
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.alert import (
    AlertEvaluationMode,
    AlertEvent,
    AlertRule,
    AlertRuleType,
    AlertScopeType,
    AlertSessionScope,
    MarketPoint,
)
from app.domain.market_data import DataStatus
from app.repositories.models import (
    AlertEvaluationRunModel,
    AlertEventModel,
    AlertRuleModel,
    MarketModel,
    SecurityModel,
)


class SqlAlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_rules(self, enabled=None):
        query = select(AlertRuleModel).order_by(AlertRuleModel.created_at, AlertRuleModel.id)
        if enabled is not None:
            query = query.where(AlertRuleModel.enabled == enabled)
        return [self._rule(row) for row in (await self.session.scalars(query)).all()]

    async def get_rule(self, rule_id):
        row = await self.session.get(AlertRuleModel, rule_id)
        return self._rule(row) if row else None

    async def save_rule(self, values, rule_id=None):
        now = datetime.now(UTC)
        row = await self.session.get(AlertRuleModel, rule_id) if rule_id else None
        if row is None:
            row = AlertRuleModel(created_at=now, **values)
            self.session.add(row)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        row.updated_at = now
        await self.session.commit()
        await self.session.refresh(row)
        return self._rule(row)

    async def delete_rule(self, rule_id):
        result = await self.session.execute(
            delete(AlertRuleModel).where(AlertRuleModel.id == rule_id)
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def set_enabled(self, rule_id, enabled):
        result = await self.session.execute(
            update(AlertRuleModel)
            .where(AlertRuleModel.id == rule_id)
            .values(enabled=enabled, updated_at=datetime.now(UTC))
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def resolve_memberships(self, rules):
        result = {}
        portfolio_ids = [r.portfolio_id for r in rules if r.portfolio_id]
        watchlist_ids = [r.watchlist_id for r in rules if r.watchlist_id]
        portfolio = {}
        if portfolio_ids:
            rows = (
                await self.session.execute(
                    text(
                        """SELECT portfolio_id,security_id,sum(CASE WHEN side='BUY' THEN quantity_shares ELSE -quantity_shares END) qty FROM portfolio_transactions WHERE portfolio_id=ANY(:ids) GROUP BY portfolio_id,security_id HAVING sum(CASE WHEN side='BUY' THEN quantity_shares ELSE -quantity_shares END)>0"""
                    ),
                    {"ids": portfolio_ids},
                )
            ).all()
            for owner, security in rows:
                portfolio.setdefault(owner, set()).add(security)
        watchlist = {}
        if watchlist_ids:
            rows = (
                await self.session.execute(
                    text(
                        "SELECT watchlist_id,security_id FROM watchlist_items WHERE watchlist_id=ANY(:ids)"
                    ),
                    {"ids": watchlist_ids},
                )
            ).all()
            for owner, security in rows:
                watchlist.setdefault(owner, set()).add(security)
        for rule in rules:
            if rule.scope_type is AlertScopeType.SECURITY:
                result[rule.id] = {rule.security_id}
            elif rule.scope_type is AlertScopeType.PORTFOLIO:
                result[rule.id] = portfolio.get(rule.portfolio_id, set())
            else:
                result[rule.id] = watchlist.get(rule.watchlist_id, set())
        return result

    async def market_history(self, security_ids, target_date, days):
        if not security_ids:
            return {}, {}
        rows = (
            await self.session.execute(
                text(
                    """SELECT p.security_id,p.trade_date,p.open,p.high,p.low,p.close,p.data_status,t.ma5,t.ma10,t.ma20,t.ma60,t.ma120,t.ma240 FROM daily_prices p LEFT JOIN technical_snapshots t ON t.security_id=p.security_id AND t.trade_date=p.trade_date AND t.price_basis='RAW' WHERE p.security_id=ANY(:ids) AND p.trade_date<=:target ORDER BY p.security_id,p.trade_date DESC"""
                ),
                {"ids": list(security_ids), "target": target_date},
            )
        ).all()
        history = {}
        for row in rows:
            bucket = history.setdefault(row.security_id, [])
            if len(bucket) < days:
                bucket.append(
                    MarketPoint(
                        row.security_id,
                        row.trade_date,
                        row.open,
                        row.high,
                        row.low,
                        row.close,
                        {
                            5: row.ma5,
                            10: row.ma10,
                            20: row.ma20,
                            60: row.ma60,
                            120: row.ma120,
                            240: row.ma240,
                        },
                        DataStatus(row.data_status),
                    )
                )
        history = {key: list(reversed(value)) for key, value in history.items()}
        info_rows = (
            await self.session.execute(
                select(SecurityModel.id, SecurityModel.code, SecurityModel.name, MarketModel.code)
                .join(MarketModel)
                .where(SecurityModel.id.in_(security_ids))
            )
        ).all()
        return history, {row.id: (row.code, row.name, row[3]) for row in info_rows}

    async def realtime_ma_contexts(self, security_ids, rules):
        from app.services.realtime_alerts import RealtimeMaContext

        if not security_ids:
            return {}, {}
        rows = (
            await self.session.execute(
                text(
                    """SELECT security_id,trade_date,close FROM daily_prices
                    WHERE security_id=ANY(:ids) AND data_status='FINAL'
                    ORDER BY security_id,trade_date DESC"""
                ),
                {"ids": list(security_ids)},
            )
        ).all()
        closes = {}
        for row in rows:
            bucket = closes.setdefault(row.security_id, [])
            if len(bucket) < 239 and row.close is not None:
                bucket.append(Decimal(row.close))
        periods = {rule.ma_period for rule in rules if rule.ma_period}
        contexts = {}
        for security_id, values in closes.items():
            for period in periods:
                prior = values[: period - 1]
                contexts[(str(security_id), period)] = RealtimeMaContext(
                    period, sum(prior, Decimal("0")), len(prior)
                )
        info_rows = (
            await self.session.execute(
                select(SecurityModel.id, SecurityModel.code, SecurityModel.name, MarketModel.code)
                .join(MarketModel)
                .where(SecurityModel.id.in_(security_ids))
            )
        ).all()
        return contexts, {row.id: (row.code, row.name, row[3]) for row in info_rows}

    async def event_exists(self, fingerprint):
        return (
            await self.session.scalar(
                select(AlertEventModel.id).where(AlertEventModel.fingerprint == fingerprint)
            )
            is not None
        )

    async def event_state(self, rule_ids, target_date, since):
        rows = (
            (
                await self.session.execute(
                    select(AlertEventModel).where(
                        AlertEventModel.alert_rule_id.in_(rule_ids),
                        or_(
                            AlertEventModel.trade_date == target_date,
                            AlertEventModel.triggered_at >= since,
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        fingerprints = {row.fingerprint for row in rows if row.trade_date == target_date}
        latest = {}
        counts = {}
        for row in rows:
            key = (row.alert_rule_id, row.security_id)
            latest[key] = max(latest.get(key, row.triggered_at), row.triggered_at)
            if row.trade_date == target_date and row.notification_eligible:
                counts[row.alert_rule_id] = counts.get(row.alert_rule_id, 0) + 1
        return fingerprints, latest, counts

    async def recent_event(self, rule_id, security_id, since):
        return (
            await self.session.scalar(
                select(AlertEventModel.id)
                .where(
                    AlertEventModel.alert_rule_id == rule_id,
                    AlertEventModel.security_id == security_id,
                    AlertEventModel.triggered_at >= since,
                )
                .limit(1)
            )
            is not None
        )

    async def daily_notification_count(self, rule_id, trade_date):
        return (
            await self.session.scalar(
                select(func.count())
                .select_from(AlertEventModel)
                .where(
                    AlertEventModel.alert_rule_id == rule_id,
                    AlertEventModel.trade_date == trade_date,
                    AlertEventModel.notification_eligible.is_(True),
                )
            )
            or 0
        )

    async def add_event(self, rule, security_id, trade_date, occurrence, fingerprint, eligible):
        now = datetime.now(UTC)
        row = AlertEventModel(
            alert_rule_id=rule.id,
            security_id=security_id,
            triggered_at=now,
            trade_date=trade_date,
            event_type=occurrence.event_type,
            trigger_price=occurrence.trigger_price,
            reference_value=occurrence.reference_value,
            reference_type=occurrence.reference_type,
            message=occurrence.message,
            data_status=occurrence.data_status,
            fingerprint=fingerprint,
            notification_eligible=eligible,
            event_metadata=occurrence.event_metadata or None,
            created_at=now,
        )
        self.session.add(row)
        return row

    async def flush(self):
        await self.session.commit()

    async def start_run(self, target):
        row = AlertEvaluationRunModel(
            started_at=datetime.now(UTC),
            target_trade_date=target,
            status="RUNNING",
            rules_evaluated=0,
            securities_evaluated=0,
            events_created=0,
            errors=0,
        )
        self.session.add(row)
        await self.session.commit()
        return row.id

    async def finish_run(self, run_id, rules, securities, events, errors):
        await self.session.execute(
            update(AlertEvaluationRunModel)
            .where(AlertEvaluationRunModel.id == run_id)
            .values(
                finished_at=datetime.now(UTC),
                status="SUCCESS" if errors == 0 else "PARTIAL",
                rules_evaluated=rules,
                securities_evaluated=securities,
                events_created=events,
                errors=errors,
            )
        )
        await self.session.commit()

    async def list_events(self, unread_only=False, limit=50, event_type=None, security=None):
        query = (
            select(AlertEventModel, SecurityModel, AlertRuleModel.evaluation_mode)
            .join(SecurityModel)
            .join(AlertRuleModel, AlertRuleModel.id == AlertEventModel.alert_rule_id)
            .order_by(AlertEventModel.triggered_at.desc(), AlertEventModel.id.desc())
            .limit(limit)
        )
        if unread_only:
            query = query.where(AlertEventModel.read_at.is_(None))
        if event_type:
            query = query.where(AlertEventModel.event_type == event_type)
        if security:
            query = query.where(SecurityModel.code == security)
        return [self._event(*row) for row in (await self.session.execute(query)).all()]

    async def mark_read(self, event_id):
        result = await self.session.execute(
            update(AlertEventModel)
            .where(AlertEventModel.id == event_id)
            .values(read_at=datetime.now(UTC))
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def mark_all_read(self):
        await self.session.execute(
            update(AlertEventModel)
            .where(AlertEventModel.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        await self.session.commit()

    @staticmethod
    def _rule(r):
        return AlertRule(
            r.id,
            r.name,
            AlertRuleType(r.rule_type),
            AlertScopeType(r.scope_type),
            r.security_id,
            r.portfolio_id,
            r.watchlist_id,
            r.ma_period,
            Decimal(r.threshold_price) if r.threshold_price is not None else None,
            Decimal(r.threshold_percent) if r.threshold_percent is not None else None,
            r.consecutive_days,
            r.enabled,
            r.cooldown_minutes,
            r.daily_limit,
            r.created_at,
            r.updated_at,
            AlertEvaluationMode(r.evaluation_mode),
            AlertSessionScope(r.session_scope),
        )

    @staticmethod
    def _event(r, s, evaluation_mode):
        return AlertEvent(
            r.id,
            r.alert_rule_id,
            r.security_id,
            s.code,
            s.name,
            r.triggered_at,
            r.trade_date,
            r.event_type,
            Decimal(r.trigger_price),
            Decimal(r.reference_value),
            r.reference_type,
            r.message,
            DataStatus(r.data_status),
            r.fingerprint,
            r.notification_eligible,
            r.read_at,
            r.created_at,
            AlertEvaluationMode(evaluation_mode),
            r.event_metadata or {},
        )
