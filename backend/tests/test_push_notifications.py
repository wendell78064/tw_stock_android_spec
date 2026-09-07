from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.adapters.fcm_push import FcmPushProvider
from app.core.errors import AppError
from app.core.settings import Settings
from app.domain.push import PushDeliveryResult, PushNotificationPayload, PushProviderType
from app.repositories.models import UserDeviceModel
from app.repositories.push_models import PushDeliveryModel, PushEventModel, PushTokenModel
from app.services.push_notifications import (
    FakePushProvider,
    PushNotificationService,
)


class MemorySession:
    def __init__(self):
        self.objects = {}
        self.added = []

    def add(self, obj):
        self.added.append(obj)
        if hasattr(obj, "id") and obj.id:
            self.objects[(type(obj), obj.id)] = obj

    async def commit(self):
        pass

    async def flush(self):
        pass

    async def get(self, model, obj_id):
        return self.objects.get((model, obj_id))

    async def scalar(self, stmt):
        res = await self.scalars(stmt)
        return res.first()

    async def scalars(self, stmt):
        entity = stmt.column_descriptions[0].get("entity") if stmt.column_descriptions else None
        if not entity:
            return SimpleNamespace(all=lambda: [], first=lambda: None)

        matched = []
        for (m, _), obj in self.objects.items():
            if m is not entity:
                continue
            matches = True
            for crit in getattr(stmt, "_where_criteria", ()):
                left = getattr(crit, "left", None)
                right = getattr(crit, "right", None)
                col_name = getattr(left, "name", None)
                val = getattr(right, "value", None)
                modifier = getattr(crit, "modifier", None)

                if modifier is not None and str(modifier) == "is_true":
                    val_col = getattr(obj, col_name, None)
                    if not bool(val_col):
                        matches = False
                        break
                    continue

                if col_name and hasattr(obj, col_name):
                    obj_val = getattr(obj, col_name)
                    if val is not None and obj_val != val:
                        matches = False
                        break
            if matches:
                matched.append(obj)
        return SimpleNamespace(all=lambda: matched, first=lambda: matched[0] if matched else None)


class FlakyPushProvider:
    def __init__(self, failures_before_success: int = 1, transient: bool = True):
        self.failures_remaining = failures_before_success
        self.transient = transient
        self.calls = 0

    @property
    def provider_type(self) -> PushProviderType:
        return PushProviderType.FCM

    @property
    def configured(self) -> bool:
        return True

    async def send(self, token: str, payload: PushNotificationPayload) -> PushDeliveryResult:
        self.calls += 1
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            return PushDeliveryResult(
                success=False,
                provider="FCM",
                error="TRANSIENT_ERROR" if self.transient else "PERMANENT_ERROR",
                retryable=self.transient,
                invalid_token=False,
            )
        return PushDeliveryResult(
            success=True,
            provider="FCM",
            message_id="fcm-msg-ok",
        )

    async def health(self):
        return {"status": "CONFIGURED", "configured": True}


class InvalidTokenProvider:
    @property
    def provider_type(self) -> PushProviderType:
        return PushProviderType.FCM

    @property
    def configured(self) -> bool:
        return True

    async def send(self, token: str, payload: PushNotificationPayload) -> PushDeliveryResult:
        return PushDeliveryResult(
            success=False,
            provider="FCM",
            error="INVALID_TOKEN",
            retryable=False,
            invalid_token=True,
        )

    async def health(self):
        return {"status": "CONFIGURED", "configured": True}


@pytest.mark.asyncio
async def test_token_registration_ownership_enforced():
    session = MemorySession()
    provider = FakePushProvider()
    service = PushNotificationService(session, provider)

    user_id = uuid4()
    other_user = uuid4()
    device_pub = "device-1"

    # 1. Reject registration if device is not owned
    with pytest.raises(AppError) as exc:
        await service.register_token(user_id, device_pub, "token-1")
    assert exc.value.code == "DEVICE_NOT_OWNED"

    # Add owned device
    dev = UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    )
    session.add(dev)

    # 2. Registration succeeds
    await service.register_token(user_id, device_pub, "token-1")
    tok = await session.scalar(select(PushTokenModel).where(PushTokenModel.token == "token-1"))
    assert tok is not None
    assert tok.active is True
    assert tok.device_public_id == device_pub

    # 3. Idempotent re-registration
    await service.register_token(user_id, device_pub, "token-1")
    assert tok.active is True

    # 4. Token conflict across users
    with pytest.raises(AppError) as exc:
        dev_other = UserDeviceModel(
            id=uuid4(),
            user_id=other_user,
            device_public_id="device-2",
            app_version="1.0",
            created_at=datetime.now(UTC),
            
            last_seen_at=datetime.now(UTC),
            revoked_at=None,
        )
        session.add(dev_other)
        await service.register_token(other_user, "device-2", "token-1")
    assert exc.value.code == "TOKEN_CONFLICT"

    # 5. Token refresh on same device
    await service.register_token(user_id, device_pub, "token-1-refreshed")
    assert tok.token == "token-1-refreshed"

    # 6. Deactivate token on unregister
    await service.unregister_token(user_id, device_pub)
    assert tok.active is False


@pytest.mark.asyncio
async def test_delivery_states_and_fcm_disabled_mode():
    session = MemorySession()
    settings = Settings(fcm_enabled=False, fcm_credentials_file=None)
    provider = FcmPushProvider(settings)
    assert provider.configured is False

    service = PushNotificationService(session, provider)
    user_id = uuid4()
    device_pub = "device-10"

    dev = UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    )
    session.add(dev)
    await service.register_token(user_id, device_pub, "token-disabled")

    # Dispatch event while FCM is disabled -> delivery marked DISABLED, never SENT
    results = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=uuid4(),
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="Test alert",
    )
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].error == "DISABLED"

    delivs = (await session.scalars(select(PushDeliveryModel))).all()
    assert len(delivs) == 1
    assert delivs[0].status == "DISABLED"
    assert delivs[0].attempts == 0


@pytest.mark.asyncio
async def test_delivery_success_and_deduplication():
    session = MemorySession()
    provider = FakePushProvider()
    service = PushNotificationService(session, provider)

    user_id = uuid4()
    device_pub = "device-20"
    session.add(UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    ))
    await service.register_token(user_id, device_pub, "tok-ok")

    event_id = uuid4()
    # 1. First dispatch -> SENT
    results = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=event_id,
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="Target reached",
    )
    assert len(results) == 1
    assert results[0].success is True
    assert len(provider.sent_messages) == 1

    deliv = (await session.scalars(select(PushDeliveryModel))).first()
    assert deliv.status == "SENT"
    assert deliv.attempts == 1

    # 2. Duplicate dispatch with same event_id -> silently dropped, not sent twice
    dup_results = await service.dispatch_alert_event(
        user_id=user_id,
        event_id=event_id,
        alert_type="PRICE_TARGET",
        security_code="2330",
        message="Target reached",
    )
    assert len(dup_results) == 0
    assert len(provider.sent_messages) == 1


@pytest.mark.asyncio
async def test_transient_failure_bounded_retry():
    session = MemorySession()
    provider = FlakyPushProvider(failures_before_success=1, transient=True)
    service = PushNotificationService(session, provider)

    user_id = uuid4()
    device_pub = "device-30"
    session.add(UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    ))
    await service.register_token(user_id, device_pub, "tok-flaky")

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)
    results = await service.deliver_event(event, max_retries=2)
    assert len(results) == 1
    assert results[0].success is True
    assert provider.calls == 2

    deliv = (await session.scalars(select(PushDeliveryModel))).first()
    assert deliv.status == "SENT"
    assert deliv.attempts == 2


@pytest.mark.asyncio
async def test_invalid_token_deactivates_token():
    session = MemorySession()
    provider = InvalidTokenProvider()
    service = PushNotificationService(session, provider)

    user_id = uuid4()
    device_pub = "device-40"
    session.add(UserDeviceModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id=device_pub,
        app_version="1.0",
        created_at=datetime.now(UTC),
        
        last_seen_at=datetime.now(UTC),
        revoked_at=None,
    ))
    await service.register_token(user_id, device_pub, "tok-invalid")
    tok = (await session.scalars(select(PushTokenModel))).first()
    assert tok.active is True

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)
    results = await service.deliver_event(event, max_retries=1)
    assert len(results) == 1
    assert results[0].success is False
    assert results[0].invalid_token is True

    assert tok.active is False
    deliv = (await session.scalars(select(PushDeliveryModel))).first()
    assert deliv.status == "INVALID_TOKEN"
    assert deliv.attempts == 1


@pytest.mark.asyncio
async def test_monitoring_user_id_unset_safe():
    session = MemorySession()
    provider = FakePushProvider()
    service = PushNotificationService(session, provider)

    # When event.user_id is None (e.g. FCM_MONITORING_USER_ID is unset), deliver_event fails safe
    event = PushEventModel(
        id=uuid4(),
        user_id=None,
        event_type="DATASET_STALE",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)
    results = await service.deliver_event(event)
    assert results == []
    assert len(provider.sent_messages) == 0


@pytest.mark.asyncio
async def test_missing_credential_file_safe_when_disabled():
    settings = Settings(
        fcm_enabled=False,
        fcm_project_id="sample-project",
        fcm_credentials_file="/nonexistent/path/serviceAccount.json",
    )
    provider = FcmPushProvider(settings)
    assert provider.configured is False

    health = await provider.health()
    assert health["status"] == "UNCONFIGURED"
    assert health["configured"] is False

    # Send attempt fails closed without accessing filesystem or raising exceptions
    res = await provider.send("tok-123", PushNotificationPayload("e1", "ALERT", "2330", "T", "B"))
    assert res.success is False
    assert res.error == "FCM_UNCONFIGURED"

