from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.push import (
    PushDeliveryResult,
    PushNotificationPayload,
    PushProviderType,
)
from app.repositories.models import UserDeviceModel


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
        self._local_dedup_set: set[str] = set()

    async def register_token(
        self,
        user_id: UUID,
        device_public_id: str,
        token: str,
        platform: str = "ANDROID",
    ) -> None:
        stmt = select(UserDeviceModel).where(
            UserDeviceModel.user_id == user_id,
            UserDeviceModel.device_public_id == device_public_id,
        )
        device = (await self.session.scalars(stmt)).first()
        now_utc = datetime.now(UTC)

        if device:
            device.push_token = token
            device.platform = platform
            device.last_seen_at = now_utc
            device.revoked_at = None
        else:
            new_device = UserDeviceModel(
                id=uuid4(),
                user_id=user_id,
                device_public_id=device_public_id,
                push_token=token,
                platform=platform,
                created_at=now_utc,
                last_seen_at=now_utc,
            )
            self.session.add(new_device)
        await self.session.commit()

    async def unregister_token(
        self, user_id: UUID, device_public_id: str
    ) -> None:
        stmt = select(UserDeviceModel).where(
            UserDeviceModel.user_id == user_id,
            UserDeviceModel.device_public_id == device_public_id,
        )
        device = (await self.session.scalars(stmt)).first()
        if device:
            device.push_token = None
            device.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def dispatch_alert_event(
        self,
        user_id: UUID,
        event_id: UUID,
        alert_type: str,
        security_code: str,
        message: str,
    ) -> list[PushDeliveryResult]:
        # 1. Deduplication check per event ID
        dedup_key = f"push_dedup:{event_id}"
        if self.redis:
            try:
                is_new = await self.redis.set(dedup_key, "1", nx=True, ex=86400)
                if not is_new:
                    return []
            except Exception:
                if str(event_id) in self._local_dedup_set:
                    return []
                self._local_dedup_set.add(str(event_id))
        else:
            if str(event_id) in self._local_dedup_set:
                return []
            self._local_dedup_set.add(str(event_id))

        # 2. Lookup active user devices with valid push tokens
        stmt = select(UserDeviceModel).where(
            UserDeviceModel.user_id == user_id,
            UserDeviceModel.revoked_at.is_(None),
            UserDeviceModel.push_token.isnot(None),
        )
        devices = (await self.session.scalars(stmt)).all()
        if not devices:
            return []

        payload = PushNotificationPayload(
            event_id=str(event_id),
            alert_type=alert_type,
            security_code=security_code,
            title=f"【台股警示】{security_code} {alert_type}",
            body=message,
        )

        results = []
        for dev in devices:
            if dev.push_token:
                res = await self.provider.send(dev.push_token, payload)
                results.append(res)

        return results
