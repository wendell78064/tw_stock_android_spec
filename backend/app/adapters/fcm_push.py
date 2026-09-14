"""Firebase implementation of the canonical push provider; lazy, fail-closed setup."""

import asyncio
from pathlib import Path
from typing import Any

from app.core.settings import Settings
from app.domain.push import PushDeliveryResult, PushNotificationPayload, PushProviderType


class FcmPushProvider:
    provider_type = PushProviderType.FCM

    def __init__(self, settings: Settings):
        self.settings = settings
        self._app: Any = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self.status == "READY"

    @property
    def status(self) -> str:
        if not self.settings.fcm_enabled:
            return "DISABLED"
        if not self.settings.fcm_project_id or not self.settings.fcm_credentials_file:
            return "UNCONFIGURED"
        if not Path(self.settings.fcm_credentials_file).is_file():
            return "UNCONFIGURED"
        return "READY"

    async def health(self) -> dict[str, Any]:
        return {
            "provider": "FCM",
            "configured": self.configured,
            "enabled": self.settings.fcm_enabled,
            "status": self.status,
        }

    async def send(self, device_token: str,
                   payload: PushNotificationPayload) -> PushDeliveryResult:
        if not self.configured:
            return PushDeliveryResult(False, "FCM", error="FCM_UNCONFIGURED", attempts=0)
        async with self._lock:
            return await asyncio.to_thread(self._send, device_token, payload)

    def _send(self, token: str, payload: PushNotificationPayload) -> PushDeliveryResult:
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging

            if self._app is None:
                self._app = firebase_admin.initialize_app(
                    credentials.Certificate(self.settings.fcm_credentials_file),
                    options={"projectId": self.settings.fcm_project_id, "httpTimeout": 10},
                    name=f"twml-{id(self)}",
                )
            message = messaging.Message(
                token=token,
                notification=messaging.Notification(
                    title=payload.title[:120], body=payload.body[:500]
                ),
                data={"event_id": payload.event_id, "event_type": payload.alert_type[:64]},
            )
            message_id = messaging.send(message, app=self._app)
            return PushDeliveryResult(True, "FCM", message_id=message_id)
        except Exception as error:
            # Exception messages may contain tokens or credential details: never retain them.
            category = type(error).__name__
            invalid = category == "UnregisteredError"
            transient = category in {"UnavailableError", "InternalError", "DeadlineExceededError"}
            return PushDeliveryResult(
                False, "FCM", error="INVALID_TOKEN" if invalid else
                "TRANSIENT" if transient else "PERMANENT", retryable=transient,
                invalid_token=invalid,
            )
