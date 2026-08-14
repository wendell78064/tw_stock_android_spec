from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.repositories.models import (
    SecurityModel,
    SyncChangeModel,
    SyncOperationModel,
    UserDeviceModel,
)
from app.services.cloud_sync import CloudSyncService


class FakeSession:

    def __init__(self):
        self.scalar_results = []
        self.objects = {}
        self.added = []
        self.sequence = 0

    async def scalar(self, statement):
        return self.scalar_results.pop(0) if self.scalar_results else None

    async def scalars(self, statement):
        entity = statement.column_descriptions[0].get("entity")
        values = [value for (kind, _), value in self.objects.items() if kind is entity]
        if entity is SyncOperationModel:
            values += [value for value in self.added if hasattr(value, "operation_id")]
        return SimpleNamespace(all=lambda: values)

    async def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def add(self, value):
        self.added.append(value)
        if hasattr(value, "id"):
            self.objects[(type(value), value.id)] = value

    async def flush(self):
        for value in self.added:
            if isinstance(value, SyncChangeModel) and value.sequence is None:
                self.sequence += 1
                value.sequence = self.sequence

    async def commit(self):
        await self.flush()


@pytest.mark.asyncio
async def test_slice2_full_personal_data_sync():
    session = FakeSession()
    service = CloudSyncService(session, page_limit=100)

    user_a, user_b, device_id = uuid4(), uuid4(), uuid4()
    device_a = SimpleNamespace(id=device_id, user_id=user_a, revoked_at=None)
    session.objects[(UserDeviceModel, device_id)] = device_a

    sec_id = uuid4()
    session.objects[(SecurityModel, sec_id)] = SimpleNamespace(id=sec_id)

    # 1. Push Portfolio & Transaction
    pf_id = uuid4()
    tx_id = uuid4()
    op_pf = uuid4()
    op_tx = uuid4()

    ops = [
        {
            "operation_id": op_pf,
            "entity_type": "PORTFOLIO",
            "entity_id": pf_id,
            "operation": "UPSERT",
            "base_version": 0,
            "payload": {
                "name": "Main Portfolio",
                "base_currency": "TWD",
                "is_default": True,
            },
        },
        {
            "operation_id": op_tx,
            "entity_type": "PORTFOLIO_TRANSACTION",
            "entity_id": tx_id,
            "operation": "UPSERT",
            "base_version": 0,
            "payload": {
                "portfolio_id": str(pf_id),
                "security_id": str(sec_id),
                "side": "BUY",
                "executed_at": datetime.now(UTC).isoformat(),
                "quantity_shares": 1000,
                "price": "950.0",
                "fee": "20.0",
                "lot_type": "BOARD_LOT",
            },
        },
    ]

    results = await service.push(user_a, device_id, ops)
    assert len(results) == 2
    assert results[0]["status"] == "ACCEPTED"
    assert results[1]["status"] == "ACCEPTED"

    # 2. Idempotency test (DUPLICATE status for identical op)
    op_pf_prior = SimpleNamespace(operation_id=op_pf, result=results[0])
    session.added.append(op_pf_prior)
    dup_results = await service.push(user_a, device_id, [ops[0]])
    assert dup_results[0]["status"] == "DUPLICATE"

    # 3. Transaction conflict test (stale base_version)
    op_conflict = uuid4()
    stale_tx = {
        "operation_id": op_conflict,
        "entity_type": "PORTFOLIO_TRANSACTION",
        "entity_id": tx_id,
        "operation": "UPSERT",
        "base_version": 0,
        "payload": {
            "portfolio_id": str(pf_id),
            "security_id": str(sec_id),
            "side": "BUY",
            "quantity_shares": 2000,
        },
    }
    session.scalar_results = [None]
    conflict_results = await service.push(user_a, device_id, [stale_tx])
    res_conflict = conflict_results[0]
    assert res_conflict["status"] == "CONFLICT"
    assert res_conflict["conflict_type"] == "STALE_VERSION"
    assert res_conflict["server_version"] == 1
    assert "position" not in res_conflict["server_value"]

    # 4. Push Alert Rule, Screener, Setting
    rule_id, screener_id, setting_id = uuid4(), uuid4(), uuid4()
    mixed_ops = [
        {
            "operation_id": uuid4(),
            "entity_type": "ALERT_RULE",
            "entity_id": rule_id,
            "operation": "UPSERT",
            "base_version": 0,
            "payload": {
                "name": "MA Break",
                "rule_type": "MA_CROSS",
                "scope_type": "SECURITY",
                "scope_id": str(sec_id),
                "threshold_price": "900.0",
                "ma_period": 20,
                "cooldown_minutes": 60,
                "daily_limit": 3,
                "enabled": True,
            },
        },
        {
            "operation_id": uuid4(),
            "entity_type": "SAVED_SCREENER",
            "entity_id": screener_id,
            "operation": "UPSERT",
            "base_version": 0,
            "payload": {
                "name": "Strong Growth",
                "expression": {"field": "close", "op": "GT", "value": 500},
                "sort_field": "close",
                "sort_direction": "DESC",
            },
        },
        {
            "operation_id": uuid4(),
            "entity_type": "USER_SETTING",
            "entity_id": setting_id,
            "operation": "UPSERT",
            "base_version": 0,
            "payload": {"key": "chart_indicators", "value": ["MA20", "RSI"]},
        },
    ]

    session.scalar_results = [None, None, None]
    mixed_res = await service.push(user_a, device_id, mixed_ops)
    assert len(mixed_res) == 3
    assert all(r["status"] == "ACCEPTED" for r in mixed_res)

    # 5. Forbidden Setting Rejection
    forbidden_op = {
        "operation_id": uuid4(),
        "entity_type": "USER_SETTING",
        "entity_id": uuid4(),
        "operation": "UPSERT",
        "base_version": 0,
        "payload": {"key": "auth_token", "value": {"token": "secret"}},
    }
    session.scalar_results = [None]
    forbidden_res = await service.push(user_a, device_id, [forbidden_op])
    assert forbidden_res[0]["status"] == "REJECTED"

    # 6. Invalid Screener AST Rejection
    invalid_ast_op = {
        "operation_id": uuid4(),
        "entity_type": "SAVED_SCREENER",
        "entity_id": uuid4(),
        "operation": "UPSERT",
        "base_version": 0,
        "payload": {
            "name": "Bad Screener",
            "expression": "SELECT * FROM users",
        },
    }
    session.scalar_results = [None]
    ast_res = await service.push(user_a, device_id, [invalid_ast_op])
    assert ast_res[0]["status"] == "REJECTED"

    # 7. Bootstrap Test
    boot_data = await service.bootstrap(user_a)
    assert len(boot_data["portfolios"]) == 1
    assert len(boot_data["portfolio_transactions"]) == 1
    assert len(boot_data["alert_rules"]) == 1
    assert len(boot_data["saved_screeners"]) == 1
    assert len(boot_data["user_settings"]) == 1
    assert boot_data["cursor"] >= 0

    # 8. User Isolation Test
    boot_data_b = await service.bootstrap(user_b)
    assert len(boot_data_b["portfolios"]) == 0
    assert len(boot_data_b["alert_rules"]) == 0
    assert len(boot_data_b["saved_screeners"]) == 0
    assert len(boot_data_b["user_settings"]) == 0
