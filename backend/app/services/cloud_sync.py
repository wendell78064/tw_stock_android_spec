from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.errors import AppError
from app.repositories.models import (
    AlertRuleModel,
    PortfolioModel,
    PortfolioTransactionModel,
    SavedScreenerModel,
    SecurityModel,
    SyncChangeModel,
    SyncOperationModel,
    UserDeviceModel,
    UserSettingModel,
    WatchlistItemModel,
    WatchlistModel,
)

ENTITY_TYPES = {
    "WATCHLIST",
    "WATCHLIST_ITEM",
    "PORTFOLIO",
    "PORTFOLIO_TRANSACTION",
    "ALERT_RULE",
    "SAVED_SCREENER",
    "USER_SETTING",
}
OPERATIONS = {"UPSERT", "DELETE"}
FORBIDDEN_SETTING_KEYS = {
    "auth_token",
    "device_id",
    "refresh_token",
    "notification_permission_state",
    "os_setting",
}


class CloudSyncService:
    def __init__(self, session, page_limit=100):
        self.session = session
        self.page_limit = page_limit

    async def push(self, user_id: UUID, device_id: UUID, operations: list[dict]) -> list[dict]:
        device = await self.session.get(UserDeviceModel, device_id)
        if device is None or device.user_id != user_id or device.revoked_at is not None:
            raise AppError("FORBIDDEN", "device is not active for this account", 403)
        operation_ids = [row["operation_id"] for row in operations]
        prior_rows = (
            await self.session.scalars(
                select(SyncOperationModel).where(
                    SyncOperationModel.user_id == user_id,
                    SyncOperationModel.operation_id.in_(operation_ids),
                )
            )
        ).all()
        priors = {row.operation_id: row for row in prior_rows}
        results = []
        for operation in operations:
            prior = priors.get(operation["operation_id"])
            results.append(await self._apply(user_id, device_id, operation, prior))
        await self.session.commit()
        return results

    async def _apply(self, user_id, device_id, operation, prior=None):
        operation_id = operation["operation_id"]
        if prior:
            return {**prior.result, "status": "DUPLICATE"}
        entity_type = operation["entity_type"]
        mutation = operation["operation"]
        if entity_type not in ENTITY_TYPES or mutation not in OPERATIONS:
            result = {"operation_id": str(operation_id), "status": "REJECTED"}
        else:
            model = self._get_model(entity_type)
            row = await self.session.get(model, operation["entity_id"])
            if row is not None and row.user_id != user_id:
                result = {"operation_id": str(operation_id), "status": "REJECTED"}
            elif row is not None and row.version != operation["base_version"]:
                result = {
                    "operation_id": str(operation_id),
                    "status": "CONFLICT",
                    "entity_id": str(row.id),
                    "client_base_version": operation["base_version"],
                    "server_version": row.version,
                    "server_value": self._payload(entity_type, row),
                    "conflict_type": "STALE_VERSION",
                }
            else:
                result = await self._mutate(user_id, entity_type, mutation, operation, row)
        self.session.add(
            SyncOperationModel(
                id=uuid4(),
                user_id=user_id,
                device_id=device_id,
                operation_id=operation_id,
                result=result,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.flush()
        return result

    async def _mutate(self, user_id, entity_type, mutation, operation, row):
        now = datetime.now(UTC)
        payload = operation.get("payload") or {}
        version = (row.version if row else 0) + 1

        if row is None:
            if mutation == "DELETE":
                return {"operation_id": str(operation["operation_id"]), "status": "REJECTED"}

            valid_created = await self._validate_and_build_model(
                user_id, entity_type, operation["entity_id"], payload, version, now
            )
            if valid_created is None:
                return {"operation_id": str(operation["operation_id"]), "status": "REJECTED"}
            row = valid_created
            self.session.add(row)
        elif mutation == "DELETE":
            row.deleted_at, row.updated_at, row.version = now, now, version
        else:
            if row.deleted_at is not None:
                return {
                    "operation_id": str(operation["operation_id"]),
                    "status": "CONFLICT",
                    "entity_id": str(row.id),
                    "client_base_version": operation["base_version"],
                    "server_version": row.version,
                    "server_value": self._payload(entity_type, row),
                    "conflict_type": "TOMBSTONED",
                }

            if not self._update_row(entity_type, row, payload):
                return {"operation_id": str(operation["operation_id"]), "status": "REJECTED"}
            row.updated_at, row.version = now, version

        await self.session.flush()
        current_payload = self._payload(entity_type, row)
        change = SyncChangeModel(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=row.id,
            operation=mutation,
            version=version,
            payload=current_payload,
            changed_at=now,
        )
        self.session.add(change)
        await self.session.flush()
        return {
            "operation_id": str(operation["operation_id"]),
            "status": "ACCEPTED",
            "entity_id": str(row.id),
            "server_version": version,
            "server_cursor": change.sequence,
        }

    async def _validate_and_build_model(
        self, user_id, entity_type, entity_id, payload, version, now
    ):
        if entity_type == "WATCHLIST":
            return WatchlistModel(
                id=entity_id,
                user_id=user_id,
                name=payload.get("name", "Watchlist"),
                sort_order=payload.get("sort_order", 0),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "WATCHLIST_ITEM":
            parent = await self.session.get(WatchlistModel, UUID(payload["watchlist_id"]))
            security = await self.session.get(SecurityModel, UUID(payload["security_id"]))
            if (
                parent is None
                or parent.user_id != user_id
                or parent.deleted_at
                or security is None
            ):
                return None
            return WatchlistItemModel(
                id=entity_id,
                user_id=user_id,
                watchlist_id=parent.id,
                security_id=security.id,
                sort_order=payload.get("sort_order", 0),
                note=payload.get("note"),
                target_price=payload.get("target_price"),
                stop_price=payload.get("stop_price"),
                add_price=payload.get("add_price"),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "PORTFOLIO":
            return PortfolioModel(
                id=entity_id,
                user_id=user_id,
                name=payload.get("name", "Portfolio"),
                base_currency=payload.get("base_currency", "TWD"),
                is_default=payload.get("is_default", False),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "PORTFOLIO_TRANSACTION":
            parent_pf = await self.session.get(PortfolioModel, UUID(payload["portfolio_id"]))
            security = await self.session.get(SecurityModel, UUID(payload["security_id"]))
            if (
                parent_pf is None
                or parent_pf.user_id != user_id
                or parent_pf.deleted_at
                or security is None
            ):
                return None
            executed_at = (
                datetime.fromisoformat(payload["executed_at"])
                if isinstance(payload.get("executed_at"), str)
                else now
            )
            return PortfolioTransactionModel(
                id=entity_id,
                user_id=user_id,
                portfolio_id=parent_pf.id,
                security_id=security.id,
                side=payload.get("side", "BUY"),
                executed_at=executed_at,
                quantity_shares=int(payload.get("quantity_shares", 0)),
                price=payload.get("price", "0.0"),
                fee=payload.get("fee", "0.0"),
                lot_type=payload.get("lot_type", "BOARD_LOT"),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "ALERT_RULE":
            sec_id = UUID(payload["security_id"]) if payload.get("security_id") else None
            pf_id = UUID(payload["portfolio_id"]) if payload.get("portfolio_id") else None
            wl_id = UUID(payload["watchlist_id"]) if payload.get("watchlist_id") else None
            if pf_id:
                pf = await self.session.get(PortfolioModel, pf_id)
                if pf is None or pf.user_id != user_id or pf.deleted_at:
                    return None
            if wl_id:
                wl = await self.session.get(WatchlistModel, wl_id)
                if wl is None or wl.user_id != user_id or wl.deleted_at:
                    return None
            return AlertRuleModel(
                id=entity_id,
                user_id=user_id,
                name=payload.get("name", "Alert Rule"),
                rule_type=payload.get("rule_type", "PRICE_THRESHOLD"),
                scope_type=payload.get("scope_type", "SECURITY"),
                security_id=sec_id,
                portfolio_id=pf_id,
                watchlist_id=wl_id,
                ma_period=payload.get("ma_period"),
                threshold_price=payload.get("threshold_price"),
                threshold_percent=payload.get("threshold_percent"),
                consecutive_days=payload.get("consecutive_days"),
                enabled=payload.get("enabled", True),
                cooldown_minutes=payload.get("cooldown_minutes", 60),
                daily_limit=payload.get("daily_limit", 5),
                evaluation_mode=payload.get("evaluation_mode", "EOD"),
                session_scope=payload.get("session_scope", "REGULAR"),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "SAVED_SCREENER":
            expr = payload.get("expression")
            if not isinstance(expr, dict) or not expr:
                return None  # Re-validate AST expression
            return SavedScreenerModel(
                id=entity_id,
                user_id=user_id,
                name=payload.get("name", "Screener"),
                description=payload.get("description"),
                expression=expr,
                sort_field=payload.get("sort_field", "code"),
                sort_direction=payload.get("sort_direction", "ASC"),
                version=version,
                created_at=now,
                updated_at=now,
            )
        if entity_type == "USER_SETTING":
            key = payload.get("key", "")
            if not key or key in FORBIDDEN_SETTING_KEYS:
                return None
            val = payload.get("value")
            if not isinstance(val, dict):
                return None
            return UserSettingModel(
                id=entity_id,
                user_id=user_id,
                key=key,
                value=val,
                version=version,
                created_at=now,
                updated_at=now,
            )
        return None

    def _update_row(self, entity_type, row, payload) -> bool:
        if entity_type == "WATCHLIST":
            for k in ("name", "sort_order"):
                if k in payload:
                    setattr(row, k, payload[k])
        elif entity_type == "WATCHLIST_ITEM":
            for k in ("sort_order", "note", "target_price", "stop_price", "add_price"):
                if k in payload:
                    setattr(row, k, payload[k])
        elif entity_type == "PORTFOLIO":
            for k in ("name", "base_currency", "is_default"):
                if k in payload:
                    setattr(row, k, payload[k])
        elif entity_type == "PORTFOLIO_TRANSACTION":
            for k in ("side", "quantity_shares", "price", "fee", "lot_type"):
                if k in payload:
                    setattr(row, k, payload[k])
            if "executed_at" in payload and isinstance(payload["executed_at"], str):
                row.executed_at = datetime.fromisoformat(payload["executed_at"])
        elif entity_type == "ALERT_RULE":
            for k in (
                "name",
                "rule_type",
                "scope_type",
                "ma_period",
                "threshold_price",
                "threshold_percent",
                "consecutive_days",
                "enabled",
                "cooldown_minutes",
                "daily_limit",
                "evaluation_mode",
                "session_scope",
            ):
                if k in payload:
                    setattr(row, k, payload[k])
        elif entity_type == "SAVED_SCREENER":
            if "expression" in payload and not isinstance(payload["expression"], dict):
                return False
            for k in ("name", "description", "expression", "sort_field", "sort_direction"):
                if k in payload:
                    setattr(row, k, payload[k])
        elif entity_type == "USER_SETTING":
            if "key" in payload and payload["key"] in FORBIDDEN_SETTING_KEYS:
                return False
            if "value" in payload and not isinstance(payload["value"], dict):
                return False
            for k in ("key", "value"):
                if k in payload:
                    setattr(row, k, payload[k])
        return True

    def _get_model(self, entity_type):
        mapping = {
            "WATCHLIST": WatchlistModel,
            "WATCHLIST_ITEM": WatchlistItemModel,
            "PORTFOLIO": PortfolioModel,
            "PORTFOLIO_TRANSACTION": PortfolioTransactionModel,
            "ALERT_RULE": AlertRuleModel,
            "SAVED_SCREENER": SavedScreenerModel,
            "USER_SETTING": UserSettingModel,
        }
        return mapping[entity_type]

    async def changes(self, user_id: UUID, cursor: int, limit: int):
        bounded = min(limit, self.page_limit)
        rows = (
            await self.session.scalars(
                select(SyncChangeModel)
                .where(SyncChangeModel.user_id == user_id, SyncChangeModel.sequence > cursor)
                .order_by(SyncChangeModel.sequence)
                .limit(bounded + 1)
            )
        ).all()
        has_more = len(rows) > bounded
        rows = rows[:bounded]
        return {
            "changes": [self._change(row) for row in rows],
            "next_cursor": rows[-1].sequence if rows else cursor,
            "has_more": has_more,
            "server_time": datetime.now(UTC).isoformat(),
        }

    async def bootstrap(self, user_id: UUID):
        groups = (
            await self.session.scalars(
                select(WatchlistModel)
                .where(WatchlistModel.user_id == user_id, WatchlistModel.deleted_at.is_(None))
                .order_by(WatchlistModel.sort_order, WatchlistModel.id)
            )
        ).all()
        items = (
            await self.session.scalars(
                select(WatchlistItemModel)
                .where(
                    WatchlistItemModel.user_id == user_id,
                    WatchlistItemModel.deleted_at.is_(None),
                )
                .order_by(WatchlistItemModel.watchlist_id, WatchlistItemModel.sort_order)
            )
        ).all()
        portfolios = (
            await self.session.scalars(
                select(PortfolioModel)
                .where(PortfolioModel.user_id == user_id, PortfolioModel.deleted_at.is_(None))
                .order_by(PortfolioModel.created_at)
            )
        ).all()
        transactions = (
            await self.session.scalars(
                select(PortfolioTransactionModel)
                .where(
                    PortfolioTransactionModel.user_id == user_id,
                    PortfolioTransactionModel.deleted_at.is_(None),
                )
                .order_by(PortfolioTransactionModel.executed_at)
            )
        ).all()
        alerts = (
            await self.session.scalars(
                select(AlertRuleModel)
                .where(AlertRuleModel.user_id == user_id, AlertRuleModel.deleted_at.is_(None))
                .order_by(AlertRuleModel.created_at)
            )
        ).all()
        screeners = (
            await self.session.scalars(
                select(SavedScreenerModel)
                .where(
                    SavedScreenerModel.user_id == user_id, SavedScreenerModel.deleted_at.is_(None)
                )
                .order_by(SavedScreenerModel.created_at)
            )
        ).all()
        settings = (
            await self.session.scalars(
                select(UserSettingModel)
                .where(UserSettingModel.user_id == user_id, UserSettingModel.deleted_at.is_(None))
                .order_by(UserSettingModel.key)
            )
        ).all()
        cursor = await self.session.scalar(
            select(func.coalesce(func.max(SyncChangeModel.sequence), 0)).where(
                SyncChangeModel.user_id == user_id
            )
        )
        return {
            "watchlists": [self._payload("WATCHLIST", row) for row in groups],
            "items": [self._payload("WATCHLIST_ITEM", row) for row in items],
            "portfolios": [self._payload("PORTFOLIO", row) for row in portfolios],
            "portfolio_transactions": [
                self._payload("PORTFOLIO_TRANSACTION", row) for row in transactions
            ],
            "alert_rules": [self._payload("ALERT_RULE", row) for row in alerts],
            "saved_screeners": [self._payload("SAVED_SCREENER", row) for row in screeners],
            "user_settings": [self._payload("USER_SETTING", row) for row in settings],
            "cursor": cursor,
            "server_time": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def _payload(entity_type, row):
        common = {
            "id": str(row.id),
            "version": row.version,
            "updated_at": row.updated_at.isoformat(),
            "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
        }
        if entity_type == "WATCHLIST":
            return {**common, "name": row.name, "sort_order": row.sort_order}
        if entity_type == "WATCHLIST_ITEM":
            return {
                **common,
                "watchlist_id": str(row.watchlist_id),
                "security_id": str(row.security_id),
                "sort_order": row.sort_order,
                "note": row.note,
                "target_price": str(row.target_price) if row.target_price is not None else None,
                "stop_price": str(row.stop_price) if row.stop_price is not None else None,
                "add_price": str(row.add_price) if row.add_price is not None else None,
            }
        if entity_type == "PORTFOLIO":
            return {
                **common,
                "name": row.name,
                "base_currency": row.base_currency,
                "is_default": row.is_default,
            }
        if entity_type == "PORTFOLIO_TRANSACTION":
            return {
                **common,
                "portfolio_id": str(row.portfolio_id),
                "security_id": str(row.security_id),
                "side": row.side,
                "executed_at": row.executed_at.isoformat(),
                "quantity_shares": row.quantity_shares,
                "price": str(row.price),
                "fee": str(row.fee),
                "lot_type": row.lot_type,
            }
        if entity_type == "ALERT_RULE":
            return {
                **common,
                "name": row.name,
                "rule_type": row.rule_type,
                "scope_type": row.scope_type,
                "security_id": str(row.security_id) if row.security_id else None,
                "portfolio_id": str(row.portfolio_id) if row.portfolio_id else None,
                "watchlist_id": str(row.watchlist_id) if row.watchlist_id else None,
                "ma_period": row.ma_period,
                "threshold_price": (
                    str(row.threshold_price) if row.threshold_price is not None else None
                ),
                "threshold_percent": (
                    str(row.threshold_percent) if row.threshold_percent is not None else None
                ),
                "consecutive_days": row.consecutive_days,
                "enabled": row.enabled,
                "cooldown_minutes": row.cooldown_minutes,
                "daily_limit": row.daily_limit,
                "evaluation_mode": row.evaluation_mode,
                "session_scope": row.session_scope,
            }
        if entity_type == "SAVED_SCREENER":
            return {
                **common,
                "name": row.name,
                "description": row.description,
                "expression": row.expression,
                "sort_field": row.sort_field,
                "sort_direction": row.sort_direction,
            }
        if entity_type == "USER_SETTING":
            return {
                **common,
                "key": row.key,
                "value": row.value,
            }
        return common

    @staticmethod
    def _change(row):
        return {
            "cursor": row.sequence,
            "entity_type": row.entity_type,
            "entity_id": str(row.entity_id),
            "operation": row.operation,
            "version": row.version,
            "payload": row.payload,
            "changed_at": row.changed_at.isoformat(),
        }
