import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog
from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError
from app.domain.push import (
    PushDeliveryResult,
    PushNotificationPayload,
    PushProviderType,
)
from app.repositories.models import UserDeviceModel
from app.repositories.push_models import PushDeliveryModel, PushEventModel, PushTokenModel

logger = structlog.get_logger()


class PushNotificationProvider(Protocol):
    @property
    def provider_type(self) -> PushProviderType: ...

    @property
    def configured(self) -> bool: ...

    async def send(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushDeliveryResult: ...

    async def health(self) -> dict[str, Any]: ...


class UnconfiguredPushProvider:
    @property
    def provider_type(self) -> PushProviderType:
        return PushProviderType.UNCONFIGURED

    @property
    def configured(self) -> bool:
        return False

    async def send(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushDeliveryResult:
        return PushDeliveryResult(
            success=False,
            provider="UNCONFIGURED",
            error="PUSH_PROVIDER_UNCONFIGURED",
        )

    async def health(self) -> dict[str, Any]:
        return {
            "status": "UNCONFIGURED",
            "provider": self.provider_type.value,
            "configured": False,
        }


class FakePushProvider:
    def __init__(self):
        self.sent_messages: list[tuple[str, PushNotificationPayload]] = []

    @property
    def provider_type(self) -> PushProviderType:
        return PushProviderType.FAKE

    @property
    def configured(self) -> bool:
        return True

    async def send(
        self, device_token: str, payload: PushNotificationPayload
    ) -> PushDeliveryResult:
        self.sent_messages.append((device_token, payload))
        return PushDeliveryResult(
            success=True,
            provider="FAKE",
            message_id=f"fake-msg-{uuid4().hex[:8]}",
        )

    async def health(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "provider": self.provider_type.value,
            "configured": True,
            "messages_sent_count": len(self.sent_messages),
        }


class PushNotificationService:
    def __init__(
        self,
        session: AsyncSession,
        provider: PushNotificationProvider,
        redis_client: Any = None,
    ):
        self.session = session
        self.provider = provider
        self.redis = redis_client

    async def register_token(
        self,
        user_id: UUID,
        device_public_id: str,
        token: str,
        platform: str = "ANDROID",
    ) -> None:
        device = await self.session.scalar(select(UserDeviceModel).where(
            UserDeviceModel.user_id == user_id,
            UserDeviceModel.device_public_id == device_public_id,
            UserDeviceModel.revoked_at.is_(None),
        ).with_for_update())
        if device is None:
            raise AppError("DEVICE_NOT_OWNED", "Register an owned active device first", 403)
        existing = await self.session.scalar(select(PushTokenModel).where(
            PushTokenModel.token == token))
        if existing and (existing.user_id != user_id or
                         existing.device_public_id != device_public_id):
            raise AppError("TOKEN_CONFLICT", "Token belongs to another installation", 409)
        setting = await self.session.scalar(select(PushTokenModel).where(
            PushTokenModel.user_id == user_id,
            PushTokenModel.device_public_id == device_public_id,
        ))
        now_utc = datetime.now(UTC)

        if setting:
            setting.token = token
            setting.platform = platform
            setting.active = True
            setting.updated_at = now_utc
            setting.last_seen_at = now_utc
        else:
            new_setting = PushTokenModel(
                id=uuid4(),
                user_id=user_id,
                device_public_id=device_public_id,
                token=token, platform=platform, active=True,
                created_at=now_utc,
                updated_at=now_utc,
                last_seen_at=now_utc,
            )
            self.session.add(new_setting)
        await self.session.commit()

    async def unregister_token(
        self, user_id: UUID, device_public_id: str
    ) -> None:
        stmt = select(PushTokenModel).where(
            PushTokenModel.user_id == user_id,
            PushTokenModel.device_public_id == device_public_id,
        )
        setting = (await self.session.scalars(stmt)).first()
        if setting:
            setting.active = False
            setting.updated_at = datetime.now(UTC)
            await self.session.commit()

    async def dispatch_alert_event(
        self,
        user_id: UUID,
        event_id: UUID,
        alert_type: str,
        security_code: str,
        message: str,
    ) -> list[PushDeliveryResult]:
        existing = await self.session.get(PushEventModel, event_id)
        if existing:
            return []
        event = PushEventModel(id=event_id, user_id=user_id, event_type=alert_type[:64],
                               title="TW Market Ledger 提醒",
                               body="有新的提醒，請開啟通知中心查看。",
                               created_at=datetime.now(UTC))
        self.session.add(event)
        await self.session.commit()
        return await self.deliver_event(event)

    async def materialize_event_deliveries(self, event_id: UUID) -> list[PushDeliveryModel]:
        """Materialize PENDING deliveries for all active tokens of an event's user.

        Safe against concurrent runs: uses row lock on PushEventModel and commits
        PENDING rows before dispatching.
        """
        event = await self.session.scalar(
            select(PushEventModel).where(PushEventModel.id == event_id).with_for_update()
        )
        if not event or event.user_id is None:
            return []

        tokens = (
            await self.session.scalars(
                select(PushTokenModel).where(
                    PushTokenModel.user_id == event.user_id,
                    PushTokenModel.active.is_(True),
                )
            )
        ).all()

        materialized: list[PushDeliveryModel] = []
        for token in tokens:
            delivery = await self.session.scalar(
                select(PushDeliveryModel).where(
                    PushDeliveryModel.event_id == event.id,
                    PushDeliveryModel.token_id == token.id,
                )
            )
            if delivery is not None:
                continue
            delivery = PushDeliveryModel(
                id=uuid4(),
                event_id=event.id,
                token_id=token.id,
                status="PENDING",
                attempts=0,
            )
            self.session.add(delivery)
            materialized.append(delivery)
        await self.session.commit()
        return materialized

    async def deliver_single_delivery(
        self,
        delivery_id: UUID,
        max_retries: int = 3,
    ) -> PushDeliveryResult:
        """Deliver one claimed delivery record.

        Transitions to SENDING before provider I/O.
        Classified under AT_LEAST_ONCE_WITH_AMBIGUOUS_DUPLICATE_WINDOW.
        """
        delivery = await self.session.scalar(
            select(PushDeliveryModel).where(PushDeliveryModel.id == delivery_id).with_for_update()
        )
        if not delivery:
            return PushDeliveryResult(
                success=False,
                provider=self.provider.provider_type.value,
                error="DELIVERY_NOT_FOUND",
            )

        if delivery.status in ("SENT", "INVALID_TOKEN"):
            return PushDeliveryResult(
                success=(delivery.status == "SENT"),
                provider=self.provider.provider_type.value,
                error=delivery.error,
                attempts=delivery.attempts,
            )

        event = await self.session.get(PushEventModel, delivery.event_id)
        token = await self.session.get(PushTokenModel, delivery.token_id)
        if not event or not token:
            delivery.status = "FAILED"
            delivery.error = "MISSING_EVENT_OR_TOKEN"
            await self.session.commit()
            return PushDeliveryResult(
                success=False,
                provider=self.provider.provider_type.value,
                error=delivery.error,
                attempts=delivery.attempts,
            )

        if not self.provider.configured:
            delivery.status = "DISABLED"
            await self.session.commit()
            return PushDeliveryResult(
                success=False,
                provider=self.provider.provider_type.value,
                error="DISABLED",
                attempts=0,
            )

        payload = PushNotificationPayload(
            str(event.id), event.event_type, "", event.title, event.body
        )
        result = PushDeliveryResult(
            success=False, provider=self.provider.provider_type.value, error="NOT_ATTEMPTED"
        )

        for attempt in range(min(max(max_retries, 0), 5) + 1):
            delivery.status = "SENDING"
            delivery.attempts += 1
            delivery.last_attempt_at = datetime.now(UTC)
            await self.session.commit()
            try:
                result = await self.provider.send(token.token, payload)
            except Exception:
                result = PushDeliveryResult(
                    False, self.provider.provider_type.value, error="PROVIDER_ERROR"
                )
            delivery.error = result.error
            delivery.message_id = result.message_id
            if result.success:
                delivery.status = "SENT"
            elif result.invalid_token:
                delivery.status = "INVALID_TOKEN"
                token.active = False
            else:
                delivery.status = "FAILED"
            await self.session.commit()
            if result.success or not result.retryable or attempt == max_retries:
                break
            await asyncio.sleep(2**attempt)
        return result

    async def deliver_event(self, event: PushEventModel, max_retries: int = 3):
        """Materialize all intended token deliveries and dispatch them."""
        if event.user_id is None:
            return []  # Monitoring recipient routing must be explicitly assigned.

        await self.materialize_event_deliveries(event.id)
        deliveries = (
            await self.session.scalars(
                select(PushDeliveryModel).where(
                    PushDeliveryModel.event_id == event.id,
                    PushDeliveryModel.status.in_(["PENDING", "SENDING"]),
                )
            )
        ).all()

        results = []
        for delivery in deliveries:
            res = await self.deliver_single_delivery(delivery.id, max_retries=max_retries)
            results.append(res)
        return results


async def drain_outbox(
    session: AsyncSession,
    provider: PushNotificationProvider,
    batch_size: int = 50,
    max_retries: int = 3,
    stale_seconds: float = 300.0,
) -> int:
    """Drain pending and stale push deliveries using delivery-level row locking.

    Step 1: Materialize PENDING deliveries for un-materialized events.
    Step 2: Lock and claim eligible PushDeliveryModel rows with FOR UPDATE SKIP LOCKED.
            Eligible rows:
            - status == 'PENDING'
            - status == 'SENDING' and last_attempt_at < (now - stale_seconds)
    Step 3: Dispatch claimed deliveries.
    """
    if not provider.configured:
        return 0

    now_utc = datetime.now(UTC)
    stale_cutoff = now_utc - timedelta(seconds=stale_seconds)

    # 1. Materialize any un-materialized events (events with no deliveries yet)
    unmaterialized_events = (
        await session.scalars(
            select(PushEventModel)
            .where(
                PushEventModel.user_id.is_not(None),
                ~exists(
                    select(PushDeliveryModel.id).where(
                        PushDeliveryModel.event_id == PushEventModel.id
                    )
                ),
            )
            .order_by(PushEventModel.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    ).all()

    service = PushNotificationService(session, provider)
    for event in unmaterialized_events:
        try:
            await service.materialize_event_deliveries(event.id)
        except Exception as exc:
            logger.error(
                "push_outbox_event_materialization_failed",
                event_id=str(event.id),
                error=str(exc),
            )

    # 2. Claim eligible deliveries (PENDING or stale SENDING)
    claim_stmt = (
        select(PushDeliveryModel)
        .where(
            or_(
                PushDeliveryModel.status == "PENDING",
                and_(
                    PushDeliveryModel.status == "SENDING",
                    PushDeliveryModel.last_attempt_at.is_not(None),
                    PushDeliveryModel.last_attempt_at < stale_cutoff,
                ),
            )
        )
        .order_by(PushDeliveryModel.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    deliveries = (await session.scalars(claim_stmt)).all()
    if not deliveries:
        return 0

    processed = 0
    for delivery in deliveries:
        try:
            await service.deliver_single_delivery(delivery.id, max_retries=max_retries)
            processed += 1
        except Exception as exc:
            logger.error(
                "push_outbox_delivery_dispatch_failed",
                delivery_id=str(delivery.id),
                error=str(exc),
            )
    return processed


class PushOutboxDispatcher:
    """Background outbox dispatcher task owned by application lifespan."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        provider: PushNotificationProvider,
        interval_seconds: float = 3.0,
        batch_size: int = 50,
        max_retries: int = 3,
        stale_seconds: float = 300.0,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.stale_seconds = stale_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        self._logger = logger

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name="push-outbox-dispatcher")
        self._logger.info(
            "push_outbox_dispatcher_started",
            interval_seconds=self.interval_seconds,
            batch_size=self.batch_size,
            stale_seconds=self.stale_seconds,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._logger.info("push_outbox_dispatcher_stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                async with self.session_factory() as session:
                    processed = await drain_outbox(
                        session=session,
                        provider=self.provider,
                        batch_size=self.batch_size,
                        max_retries=self.max_retries,
                        stale_seconds=self.stale_seconds,
                    )
                    if processed > 0:
                        self._logger.info("push_outbox_drained_batch", count=processed)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.error("push_outbox_dispatcher_iteration_error", error=str(exc))

            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break
