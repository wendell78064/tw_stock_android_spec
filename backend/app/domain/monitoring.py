from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class AnomalySeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AnomalyStatus(StrEnum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class AnomalyType(StrEnum):
    # Pipeline & Ingestion anomalies
    PIPELINE_FAILED = "PIPELINE_FAILED"
    INGESTION_RUN_FAILED = "INGESTION_RUN_FAILED"

    # Dataset audit anomalies
    DATASET_PARTIAL = "DATASET_PARTIAL"
    DATASET_FAILED = "DATASET_FAILED"
    DATASET_STALE = "DATASET_STALE"
    DATASET_NO_DATA = "DATASET_NO_DATA"

    # Precision repair anomalies
    REPAIR_FAILED = "REPAIR_FAILED"
    REPAIR_PARTIAL = "REPAIR_PARTIAL"

    # Duplicates and technicals
    DUPLICATE_RECORDS = "DUPLICATE_RECORDS"
    TECHNICAL_GAP = "TECHNICAL_GAP"


@dataclass(frozen=True)
class AnomalyEvent:
    anomaly_type: AnomalyType
    dataset: str
    target_date: date
    severity: AnomalySeverity
    scope_key: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    event_id: UUID = field(default_factory=uuid4)

    @property
    def dedupe_key(self) -> str:
        """Stable canonical deduplication key:
        {anomaly_type}|{dataset}|{scope_key}|{target_date}
        """
        t_date = self.target_date.isoformat()
        return f"{self.anomaly_type.value}|{self.dataset}|{self.scope_key}|{t_date}"


@dataclass
class AnomalyRecord:
    id: UUID
    dedupe_key: str
    anomaly_type: str
    dataset: str
    scope_key: str
    target_date: date
    severity: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    occurrence_count: int
    last_notified_at: datetime | None = None
    resolved_at: datetime | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationEvent:
    event_id: UUID
    anomaly_type: str
    severity: AnomalySeverity
    dedupe_key: str
    title: str
    body: str
    target_date: date
    dataset: str
    created_at: datetime
    occurrence_count: int
    is_resolution: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        def _serialize(val: Any) -> Any:
            if isinstance(val, date | datetime):
                return val.isoformat()
            if isinstance(val, UUID):
                return str(val)
            if isinstance(val, StrEnum):
                return str(val)
            if isinstance(val, dict):
                return {k: _serialize(v) for k, v in val.items()}
            if isinstance(val, list):
                return [_serialize(item) for item in val]
            return val

        return _serialize(data)


@dataclass
class MonitoringRunResult:
    target_date: date
    anomalies_detected: int
    anomalies_active: int
    anomalies_new: int
    anomalies_resolved: int
    notifications_created: int
    notifications_suppressed: int
    notifications: list[NotificationEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_date": self.target_date.isoformat(),
            "anomalies_detected": self.anomalies_detected,
            "anomalies_active": self.anomalies_active,
            "anomalies_new": self.anomalies_new,
            "anomalies_resolved": self.anomalies_resolved,
            "notifications_created": self.notifications_created,
            "notifications_suppressed": self.notifications_suppressed,
            "notifications": [n.to_dict() for n in self.notifications],
        }
