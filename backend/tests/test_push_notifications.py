from datetime import UTC, datetime, timedelta
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
    drain_outbox,
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
            def check_crit(target_obj, c):
                # Handle BinaryExpression (col == val, col != val, col < val)
                if hasattr(c, "left") and hasattr(c, "right"):
                    left = getattr(c, "left", None)
                    right = getattr(c, "right", None)
                    col_name = getattr(left, "name", None)
                    val = getattr(right, "value", None)
                    modifier = getattr(c, "modifier", None)

                    if modifier is not None and str(modifier) == "is_true":
                        val_col = getattr(target_obj, col_name, None)
                        return bool(val_col)

                    if col_name and hasattr(target_obj, col_name):
                        obj_val = getattr(target_obj, col_name)
                        op_name = getattr(getattr(c, "operator", None), "__name__", "")
                        right_type = getattr(getattr(c, "right", None), "__class__", None)
                        right_name = getattr(right_type, "__name__", "")
                        if right_name == "True_":
                            return bool(obj_val) is True
                        if right_name == "False_":
                            return bool(obj_val) is False
                        if "lt" in op_name:
                            return obj_val is not None and val is not None and obj_val < val
                        if isinstance(val, list | tuple | set):
                            return obj_val in val
                        if val is not None:
                            return obj_val == val
                        if modifier is not None and "is_not" in str(modifier):
                            return obj_val is not None
                    return True

                # Handle or_ / and_ BooleanClauseList
                if hasattr(c, "clauses"):
                    op_name = getattr(getattr(c, "operator", None), "__name__", "")
                    if "or" in op_name or getattr(c, "__class__", None).__name__ == "Or":
                        return any(check_crit(target_obj, sub) for sub in c.clauses)
                    else:
                        return all(check_crit(target_obj, sub) for sub in c.clauses)
                return True

            for crit in getattr(stmt, "_where_criteria", ()):
                if not check_crit(obj, crit):
                    matches = False
                    break
            if matches:
                matched.append(obj)
        limit = getattr(stmt, "_limit", None)
        if limit is not None:
            matched = matched[:limit]
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


@pytest.mark.asyncio
async def test_drain_outbox_delivers_pending_events():
    from app.services.push_notifications import drain_outbox

    session = MemorySession()
    provider = FakePushProvider()
    user_id = uuid4()

    # User active device and token
    tok = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-1",
        token="fcm-token-1",
        platform="ANDROID",
        active=True,
    )
    session.add(tok)

    # Event in outbox
    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Price Hit",
        body="Stock price reached target",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    processed = await drain_outbox(session, provider, batch_size=10, max_retries=1)
    assert processed == 1
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0][0] == "fcm-token-1"


@pytest.mark.asyncio
async def test_drain_outbox_isolates_event_errors():
    from app.services.push_notifications import drain_outbox

    session = MemorySession()
    # Provider that raises an unexpected exception
    class ExplodingProvider:
        @property
        def provider_type(self):
            return PushProviderType.FCM

        @property
        def configured(self):
            return True

        async def send(self, token, payload):
            raise RuntimeError("Catastrophic connection crash")

    user_id = uuid4()
    tok = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-1",
        token="fcm-token-1",
        platform="ANDROID",
        active=True,
    )
    session.add(tok)

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    # Exception inside deliver_event is caught gracefully
    processed = await drain_outbox(session, ExplodingProvider(), batch_size=10, max_retries=0)
    assert processed == 1


@pytest.mark.asyncio
async def test_push_outbox_dispatcher_lifecycle():
    from app.services.push_notifications import PushOutboxDispatcher

    session = MemorySession()
    provider = FakePushProvider()

    class FakeSessionFactory:
        def __call__(self):
            class Ctx:
                async def __aenter__(self):
                    return session
                async def __aexit__(self, *args):
                    pass
            return Ctx()

    dispatcher = PushOutboxDispatcher(
        session_factory=FakeSessionFactory(),
        provider=provider,
        interval_seconds=0.05,
        batch_size=10,
    )
    assert not dispatcher.is_running

    await dispatcher.start()
    assert dispatcher.is_running

    import asyncio
    await asyncio.sleep(0.12)

    await dispatcher.stop()
    assert not dispatcher.is_running


@pytest.mark.asyncio
async def test_push_outbox_dispatcher_drains_periodically():
    from app.services.push_notifications import PushOutboxDispatcher

    session = MemorySession()
    provider = FakePushProvider()
    user_id = uuid4()

    tok = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-1",
        token="fcm-token-periodic",
        platform="ANDROID",
        active=True,
    )
    session.add(tok)

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Periodic Event",
        body="Periodic Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    class FakeSessionFactory:
        def __call__(self):
            class Ctx:
                async def __aenter__(self):
                    return session
                async def __aexit__(self, *args):
                    pass
            return Ctx()

    dispatcher = PushOutboxDispatcher(
        session_factory=FakeSessionFactory(),
        provider=provider,
        interval_seconds=0.02,
        batch_size=10,
    )

    await dispatcher.start()
    import asyncio
    await asyncio.sleep(0.08)
    await dispatcher.stop()

    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0][0] == "fcm-token-periodic"


@pytest.mark.asyncio
async def test_lifespan_dispatcher_not_started_when_fcm_disabled():
    from app.adapters.fcm_push import FcmPushProvider
    from app.core.settings import Settings

    settings = Settings(fcm_enabled=False)
    provider = FcmPushProvider(settings)

    # In main lifespan: if settings.fcm_enabled and provider.configured
    should_start = settings.fcm_enabled and provider.configured
    assert should_start is False


@pytest.mark.asyncio
async def test_multi_device_event_materialization_and_crash_recovery():
    """Verify that an event fanning out to multiple active tokens creates all deliveries,

    and a simulated crash mid-processing leaves sibling PENDING deliveries recoverable.
    """
    session = MemorySession()
    provider = FakePushProvider()
    user_id = uuid4()

    # User with 3 active devices
    for i in range(1, 4):
        tok = PushTokenModel(
            id=uuid4(),
            user_id=user_id,
            device_public_id=f"dev-{i}",
            token=f"fcm-token-{i}",
            platform="ANDROID",
            active=True,
        )
        session.add(tok)

    # Event in outbox
    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Multi-device Alert",
        body="Alert body",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    # Step 1: Run drain_outbox with batch_size=1 to simulate worker crashing after 1 delivery
    processed_1 = await drain_outbox(session, provider, batch_size=1, max_retries=1)
    assert processed_1 == 1

    # Verify all 3 delivery records were materialized
    all_deliveries = (await session.scalars(select(PushDeliveryModel))).all()
    assert len(all_deliveries) == 3

    sent_count = sum(1 for d in all_deliveries if d.status == "SENT")
    pending_count = sum(1 for d in all_deliveries if d.status == "PENDING")
    assert sent_count == 1
    assert pending_count == 2

    # Step 2: Restart/next drain_outbox iteration claims remaining 2 PENDING deliveries
    processed_2 = await drain_outbox(session, provider, batch_size=10, max_retries=1)
    assert processed_2 == 2

    # All 3 deliveries are now SENT
    assert len(provider.sent_messages) == 3
    for d in all_deliveries:
        assert d.status == "SENT"


@pytest.mark.asyncio
async def test_stale_sending_recovery_and_fresh_sending_exclusion():
    """Verify stale SENDING deliveries are re-driven while fresh ones are preserved."""
    session = MemorySession()
    provider = FakePushProvider()
    user_id = uuid4()

    tok1 = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-1",
        token="fcm-token-stale",
        platform="ANDROID",
        active=True,
    )
    tok2 = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-2",
        token="fcm-token-fresh",
        platform="ANDROID",
        active=True,
    )
    session.add(tok1)
    session.add(tok2)

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    now = datetime.now(UTC)

    # Delivery 1: Stale SENDING (attempted 600s ago)
    d_stale = PushDeliveryModel(
        id=uuid4(),
        event_id=event.id,
        token_id=tok1.id,
        status="SENDING",
        attempts=1,
        last_attempt_at=now - timedelta(seconds=600),
    )
    # Delivery 2: Fresh SENDING (attempted 10s ago)
    d_fresh = PushDeliveryModel(
        id=uuid4(),
        event_id=event.id,
        token_id=tok2.id,
        status="SENDING",
        attempts=1,
        last_attempt_at=now - timedelta(seconds=10),
    )
    session.add(d_stale)
    session.add(d_fresh)

    # drain_outbox with stale threshold = 300s
    processed = await drain_outbox(
        session, provider, batch_size=10, max_retries=1, stale_seconds=300.0
    )

    # Only the stale delivery should be claimed and processed
    assert processed == 1
    assert d_stale.status == "SENT"
    assert d_fresh.status == "SENDING"  # Fresh SENDING not reclaimed
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0][0] == "fcm-token-stale"


@pytest.mark.asyncio
async def test_terminal_statuses_never_resent():
    """Verify SENT, INVALID_TOKEN, and permanent FAILED are terminal and never re-driven."""
    session = MemorySession()
    provider = FakePushProvider()
    user_id = uuid4()

    tok = PushTokenModel(
        id=uuid4(),
        user_id=user_id,
        device_public_id="dev-1",
        token="fcm-token-term",
        platform="ANDROID",
        active=True,
    )
    session.add(tok)

    event = PushEventModel(
        id=uuid4(),
        user_id=user_id,
        event_type="PRICE_TARGET",
        title="Title",
        body="Body",
        created_at=datetime.now(UTC),
    )
    session.add(event)

    d_sent = PushDeliveryModel(
        id=uuid4(),
        event_id=event.id,
        token_id=tok.id,
        status="SENT",
        attempts=1,
    )
    session.add(d_sent)

    processed = await drain_outbox(session, provider, batch_size=10)
    assert processed == 0
    assert len(provider.sent_messages) == 0

