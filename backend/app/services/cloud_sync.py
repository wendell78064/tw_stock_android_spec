from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select

from app.core.errors import AppError
from app.repositories.models import (
    SecurityModel,
    SyncChangeModel,
    SyncOperationModel,
    UserDeviceModel,
    WatchlistItemModel,
    WatchlistModel,
)

ENTITY_TYPES = {"WATCHLIST", "WATCHLIST_ITEM"}
OPERATIONS = {"UPSERT", "DELETE"}


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
            results.append(await self._apply(user_id, device_id, operation, priors.get(operation["operation_id"])))
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
            model = WatchlistModel if entity_type == "WATCHLIST" else WatchlistItemModel
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
            if entity_type == "WATCHLIST":
                row = WatchlistModel(
                    id=operation["entity_id"],
                    user_id=user_id,
                    name=payload["name"],
                    sort_order=payload.get("sort_order", 0),
                    version=version,
                    created_at=now,
                    updated_at=now,
                )
            else:
                parent = await self.session.get(WatchlistModel, UUID(payload["watchlist_id"]))
                security = await self.session.get(SecurityModel, UUID(payload["security_id"]))
                if (
                    parent is None
                    or parent.user_id != user_id
                    or parent.deleted_at
                    or security is None
                ):
                    return {"operation_id": str(operation["operation_id"]), "status": "REJECTED"}
                row = WatchlistItemModel(
                    id=operation["entity_id"],
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
            allowed = (
                ("name", "sort_order")
                if entity_type == "WATCHLIST"
                else ("sort_order", "note", "target_price", "stop_price", "add_price")
            )
            for key in allowed:
                if key in payload:
                    setattr(row, key, payload[key])
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
        cursor = await self.session.scalar(
            select(func.coalesce(func.max(SyncChangeModel.sequence), 0)).where(
                SyncChangeModel.user_id == user_id
            )
        )
        return {
            "watchlists": [self._payload("WATCHLIST", row) for row in groups],
            "items": [self._payload("WATCHLIST_ITEM", row) for row in items],
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
