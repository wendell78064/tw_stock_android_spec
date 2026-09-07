from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.push import (
    PushDeliveryResult,
    PushNotificationPayload,
    PushProviderType,
)
from app.repositories.models import UserDeviceModel
from app.repositories.push_models import PushDeliveryModel, PushEventModel, PushTokenModel


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

    async def deliver_event(self, event: PushEventModel, max_retries: int = 3):
        """One bounded dispatch. Row locks serialize concurrent dispatchers.

        SENDING is persisted before I/O. An interrupted/ambiguous attempt is not replayed
        automatically, since FCM cannot provide exactly-once delivery.
        """
        if event.user_id is None:
            return []  # Monitoring recipient routing must be explicitly assigned.
        await self.session.scalar(select(PushEventModel).where(
            PushEventModel.id == event.id).with_for_update())
        tokens = (await self.session.scalars(select(PushTokenModel).where(
            PushTokenModel.user_id == event.user_id, PushTokenModel.active.is_(True)
        ))).all()
        pending = []
        for token in tokens:
            delivery = await self.session.scalar(select(PushDeliveryModel).where(
                PushDeliveryModel.event_id == event.id, PushDeliveryModel.token_id == token.id))
            if delivery is not None:
                continue
            delivery = PushDeliveryModel(id=uuid4(), event_id=event.id, token_id=token.id,
                                         status="PENDING", attempts=0)
            self.session.add(delivery)
            pending.append((token, delivery))
        await self.session.commit()
        results = []
        for token, delivery in pending:
            if not self.provider.configured:
                delivery.status = "DISABLED"
                await self.session.commit()
                results.append(PushDeliveryResult(False, self.provider.provider_type.value,
                                                  error="DISABLED", attempts=0))
                continue
            payload = PushNotificationPayload(str(event.id), event.event_type, "",
                                              event.title, event.body)
            for attempt in range(min(max(max_retries, 0), 5) + 1):
                delivery.status = "SENDING"
                delivery.attempts += 1
                delivery.last_attempt_at = datetime.now(UTC)
                await self.session.commit()
                try:
                    result = await self.provider.send(token.token, payload)
                except Exception:
                    result = PushDeliveryResult(False, self.provider.provider_type.value,
                                                error="PROVIDER_ERROR")
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
                import asyncio
                await asyncio.sleep(2 ** attempt)
            results.append(result)
        return results
