from dataclasses import dataclass
from enum import StrEnum


class PushProviderType(StrEnum):
    UNCONFIGURED = "UNCONFIGURED"
    FAKE = "FAKE"
    FCM = "FCM"


@dataclass(frozen=True)
class PushNotificationPayload:
    event_id: str
    alert_type: str
    security_code: str
    title: str
    body: str


@dataclass(frozen=True)
class PushDeliveryResult:
    success: bool
    provider: str
    message_id: str | None = None
    error: str | None = None
