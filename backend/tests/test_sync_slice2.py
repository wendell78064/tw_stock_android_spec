from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.repositories.models import (
    AuthSessionModel,
    SecurityModel,
    UserDeviceModel,
    UserModel,
)


@pytest.mark.asyncio
async def test_slice2_full_personal_data_sync(db_session):
    # Setup test security & users
    sec_id = uuid4()
    security = SecurityModel(
        id=sec_id,
        code="2330",
        name="TSMC",
        market="TWSE",
        security_type="COMMON_STOCK",
        is_active=True,
    )
    user_a = UserModel(
        id=uuid4(), login_identifier="usera@example.com", password_hash="hash", status="ACTIVE"
    )
    user_b = UserModel(
        id=uuid4(), login_identifier="userb@example.com", password_hash="hash", status="ACTIVE"
    )
    device_a = UserDeviceModel(
        id=uuid4(),
        user_id=user_a.id,
        device_public_id="dev_a_id",
        name="Phone A",
        platform="ANDROID",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    device_b = UserDeviceModel(
        id=uuid4(),
        user_id=user_a.id,
        device_public_id="dev_b_id",
        name="Phone B",
        platform="ANDROID",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    session_a = AuthSessionModel(
        id=uuid4(),
        user_id=user_a.id,
        refresh_token_hash="hash_a",
        expires_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )
    db_session.add_all([security, user_a, user_b, device_a, device_b, session_a])
    await db_session.commit()

    token_a = create_access_token(user_a.id, session_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        headers = {"Authorization": f"Bearer {token_a}"}

        # 1. Push Portfolio & Transaction
        pf_id = uuid4()
        tx_id = uuid4()
        op_pf = uuid4()
        op_tx = uuid4()

        push_resp = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_a.id),
                "operations": [
                    {
                        "operation_id": str(op_pf),
                        "entity_type": "PORTFOLIO",
                        "entity_id": str(pf_id),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {
                            "name": "Main Portfolio",
                            "base_currency": "TWD",
                            "is_default": True,
                        },
                    },
                    {
                        "operation_id": str(op_tx),
                        "entity_type": "PORTFOLIO_TRANSACTION",
                        "entity_id": str(tx_id),
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
                ],
            },
        )
        assert push_resp.status_code == 200
        results = push_resp.json()["data"]["results"]
        assert len(results) == 2
        assert results[0]["status"] == "ACCEPTED"
        assert results[1]["status"] == "ACCEPTED"

        # 2. Idempotency test (repeating same operations)
        push_dup = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_a.id),
                "operations": [
                    {
                        "operation_id": str(op_pf),
                        "entity_type": "PORTFOLIO",
                        "entity_id": str(pf_id),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {"name": "Main Portfolio"},
                    }
                ],
            },
        )
        assert push_dup.json()["data"]["results"][0]["status"] == "DUPLICATE"

        # 3. Portfolio Transaction Conflict test (stale base_version)
        op_conflict = uuid4()
        push_conflict = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_b.id),
                "operations": [
                    {
                        "operation_id": str(op_conflict),
                        "entity_type": "PORTFOLIO_TRANSACTION",
                        "entity_id": str(tx_id),
                        "operation": "UPSERT",
                        "base_version": 0,  # Stale version! Current version is 1
                        "payload": {
                            "portfolio_id": str(pf_id),
                            "security_id": str(sec_id),
                            "side": "BUY",
                            "quantity_shares": 2000,
                        },
                    }
                ],
            },
        )
        res_conflict = push_conflict.json()["data"]["results"][0]
        assert res_conflict["status"] == "CONFLICT"
        assert res_conflict["conflict_type"] == "STALE_VERSION"
        assert res_conflict["server_version"] == 1
        # Derived state must NOT be in server_value
        assert "position" not in res_conflict["server_value"]
        assert "realized_pnl" not in res_conflict["server_value"]

        # 4. Push Alert Rule, Screener, and Setting
        rule_id = uuid4()
        screener_id = uuid4()
        setting_id = uuid4()

        push_mixed = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_a.id),
                "operations": [
                    {
                        "operation_id": str(uuid4()),
                        "entity_type": "ALERT_RULE",
                        "entity_id": str(rule_id),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {
                            "name": "TSMC High Alert",
                            "rule_type": "PRICE_THRESHOLD",
                            "scope_type": "SECURITY",
                            "security_id": str(sec_id),
                            "portfolio_id": str(pf_id),
                            "threshold_price": "1000.0",
                            "evaluation_mode": "REALTIME",
                            "enabled": True,
                        },
                    },
                    {
                        "operation_id": str(uuid4()),
                        "entity_type": "SAVED_SCREENER",
                        "entity_id": str(screener_id),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {
                            "name": "High Volume Tech",
                            "expression": {"operator": "AND", "conditions": []},
                            "sort_field": "turnover",
                        },
                    },
                    {
                        "operation_id": str(uuid4()),
                        "entity_type": "USER_SETTING",
                        "entity_id": str(setting_id),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {"key": "chart_indicators", "value": {"ma": [5, 20, 60]}},
                    },
                ],
            },
        )
        res_mixed = push_mixed.json()["data"]["results"]
        assert all(r["status"] == "ACCEPTED" for r in res_mixed)

        # 5. Device-Local / Credentials setting rejection
        push_forbidden_setting = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_a.id),
                "operations": [
                    {
                        "operation_id": str(uuid4()),
                        "entity_type": "USER_SETTING",
                        "entity_id": str(uuid4()),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {"key": "auth_token", "value": {"token": "secret"}},
                    }
                ],
            },
        )
        assert push_forbidden_setting.json()["data"]["results"][0]["status"] == "REJECTED"

        # 6. Invalid Screener AST rejection
        push_invalid_screener = await client.post(
            "/v1/sync/push",
            headers=headers,
            json={
                "device_id": str(device_a.id),
                "operations": [
                    {
                        "operation_id": str(uuid4()),
                        "entity_type": "SAVED_SCREENER",
                        "entity_id": str(uuid4()),
                        "operation": "UPSERT",
                        "base_version": 0,
                        "payload": {
                            "name": "Bad Screener",
                            "expression": "SELECT * FROM users",  # Invalid raw string!
                        },
                    }
                ],
            },
        )
        assert push_invalid_screener.json()["data"]["results"][0]["status"] == "REJECTED"

        # 7. Bootstrap Test for Device B
        boot_resp = await client.get("/v1/sync/bootstrap", headers=headers)
        assert boot_resp.status_code == 200
        bdata = boot_resp.json()["data"]
        assert len(bdata["portfolios"]) == 1
        assert len(bdata["portfolio_transactions"]) == 1
        assert len(bdata["alert_rules"]) == 1
        assert len(bdata["saved_screeners"]) == 1
        assert len(bdata["user_settings"]) == 1
        assert bdata["cursor"] > 0

        # 8. User B Isolation Test (User B cannot see or alter User A data)
        session_b = AuthSessionModel(
            id=uuid4(),
            user_id=user_b.id,
            refresh_token_hash="hash_b",
            expires_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
        )
        db_session.add(session_b)
        await db_session.commit()

        token_b = create_access_token(user_b.id, session_b.id)
        headers_b = {"Authorization": f"Bearer {token_b}"}

        boot_b = await client.get("/v1/sync/bootstrap", headers=headers_b)
        bdata_b = boot_b.json()["data"]
        assert len(bdata_b["portfolios"]) == 0
        assert len(bdata_b["alert_rules"]) == 0
        assert len(bdata_b["saved_screeners"]) == 0
        assert len(bdata_b["user_settings"]) == 0
