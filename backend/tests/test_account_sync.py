from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest

from app.core.errors import AppError
from app.repositories.models import (
    AuthSessionModel,
    SyncChangeModel,
    SyncOperationModel,
    UserDeviceModel,
    UserModel,
    WatchlistModel,
)
from app.services.auth import AuthService
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
async def test_register_password_hash_duplicate_and_login_rotation_logout():
    session = FakeSession()
    service = AuthService(session, "test-secret-that-is-not-production")
    user = await service.register(" User@Example.com ", "correct horse battery staple")
    assert user.login_identifier == "user@example.com"
    assert user.password_hash != "correct horse battery staple"
    session.scalar_results = [user]
    tokens = await service.login("USER@example.com", "correct horse battery staple")
    claims = jwt.decode(tokens["access_token"], service.secret, algorithms=["HS256"])
    auth_session = next(value for value in session.added if isinstance(value, AuthSessionModel))
    session.objects[(UserModel, user.id)] = user
    session.objects[(AuthSessionModel, auth_session.id)] = auth_session
    assert (await service.authenticate(tokens["access_token"])).id == user.id
    session.scalar_results = [auth_session]
    rotated = await service.refresh(tokens["refresh_token"])
    assert rotated["refresh_token"] != tokens["refresh_token"] and auth_session.revoked_at
    session.scalar_results = [auth_session]
    with pytest.raises(AppError):
        await service.refresh(tokens["refresh_token"])
    newest = [value for value in session.added if isinstance(value, AuthSessionModel)][-1]
    session.scalar_results = [newest]
    await service.logout(rotated["refresh_token"])
    assert newest.revoked_at is not None and claims["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_auth_rejects_duplicate_wrong_expired_and_disabled():
    session = FakeSession()
    service = AuthService(session, "test-secret")
    session.scalar_results = [uuid4()]
    with pytest.raises(AppError) as duplicate:
        await service.register("same@example.com", "correct horse battery staple")
    assert duplicate.value.args[0] == "ACCOUNT_EXISTS"
    password_hash = service.passwords.hash("correct horse battery staple")
    user = SimpleNamespace(
        id=uuid4(), login_identifier="a@b.c", password_hash=password_hash, status="ACTIVE"
    )
    session.scalar_results = [user]
    with pytest.raises(AppError):
        await service.login("a@b.c", "wrong password")
    expired = jwt.encode(
        {
            "sub": str(user.id),
            "sid": str(uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        service.secret,
        algorithm="HS256",
    )
    with pytest.raises(AppError):
        await service.authenticate(expired)
    user.status = "DISABLED"
    session.scalar_results = [user]
    with pytest.raises(AppError) as disabled:
        await service.login("a@b.c", "correct horse battery staple")
    assert disabled.value.args[2] == 403


@pytest.mark.asyncio
async def test_device_upsert_two_devices_and_revoked_boundary():
    session = FakeSession()
    service = AuthService(session, "test-secret")
    user_id = uuid4()
    session.scalar_results = [None]
    first = await service.upsert_device(user_id, "device-public-id-0001", "A", "ANDROID", "1")
    session.scalar_results = [first]
    same = await service.upsert_device(user_id, "device-public-id-0001", "A2", "ANDROID", "2")
    session.scalar_results = [None]
    second = await service.upsert_device(user_id, "device-public-id-0002", "B", "ANDROID", "1")
    assert first.id == same.id and first.name == "A2" and second.id != first.id


@pytest.mark.asyncio
async def test_sync_create_conflict_tombstone_idempotency_and_user_isolation():
    session = FakeSession()
    service = CloudSyncService(session, page_limit=100)
    user_a, user_b, device_id = uuid4(), uuid4(), uuid4()
    device = SimpleNamespace(id=device_id, user_id=user_a, revoked_at=None)
    session.objects[(UserDeviceModel, device_id)] = device
    entity_id, operation_id = uuid4(), uuid4()
    create = {
        "operation_id": operation_id,
        "entity_type": "WATCHLIST",
        "entity_id": entity_id,
        "operation": "UPSERT",
        "base_version": 0,
        "payload": {"name": "A", "sort_order": 0},
    }
    accepted = (await service.push(user_a, device_id, [create]))[0]
    row = session.objects[(WatchlistModel, entity_id)]
    assert accepted["status"] == "ACCEPTED" and row.version == 1
    prior = SimpleNamespace(operation_id=operation_id, result=accepted)
    session.added.append(prior)
    assert (await service.push(user_a, device_id, [create]))[0]["status"] == "DUPLICATE"
    stale = {**create, "operation_id": uuid4(), "base_version": 0, "payload": {"name": "B"}}
    session.scalar_results = [None]
    assert (await service.push(user_a, device_id, [stale]))[0]["status"] == "CONFLICT"
    delete = {**create, "operation_id": uuid4(), "operation": "DELETE", "base_version": 1}
    session.scalar_results = [None]
    assert (await service.push(user_a, device_id, [delete]))[0]["status"] == "ACCEPTED"
    assert row.deleted_at is not None and row.version == 2
    cross_user = {**create, "operation_id": uuid4(), "base_version": 2}
    device.user_id = user_b
    session.scalar_results = [None]
    assert (await service.push(user_b, device_id, [cross_user]))[0]["status"] == "REJECTED"


def test_sync_page_limit_and_cursor_contract():
    service = CloudSyncService(FakeSession(), page_limit=100)
    assert service.page_limit == 100
