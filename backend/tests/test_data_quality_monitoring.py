from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.cli.monitor_data_quality import print_human_monitoring_result
from app.domain.audit import (
    AuditStatus,
    DailyDataAuditReport,
    DailyPriceMarketAudit,
    DerivativesDatasetAudit,
    DuplicateAudit,
    IndustryStrengthAudit,
    MarketSpotAudit,
    SecurityMasterAudit,
    TechnicalsAudit,
)
from app.domain.monitoring import (
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    MonitoringRunResult,
    NotificationEvent,
)
from app.repositories.models import DataQualityAnomalyModel, IngestionRunModel
from app.services.data_quality_monitoring import DataQualityMonitoringService


class MockTradingCalendar:
    def __init__(self, non_trading_dates: set[date] | None = None):
        self.non_trading_dates = non_trading_dates or set()

    def is_trading_day(self, value: date) -> bool:
        if value in self.non_trading_dates:
            return False
        return value.weekday() < 5


def _build_clean_audit_report(target_date: date) -> DailyDataAuditReport:
    return DailyDataAuditReport(
        target_date=target_date,
        is_trading_day=True,
        day_type="TRADING_DAY",
        security_master=SecurityMasterAudit(
            total_securities=1900,
            active_common_stocks=1800,
            twse_common_stocks=1000,
            tpex_common_stocks=800,
            inactive_securities=100,
            duplicate_count=0,
            status=AuditStatus.COMPLETE,
        ),
        twse_daily=DailyPriceMarketAudit(
            market="TWSE",
            active_common_stocks=1000,
            expected_eligible=1000,
            rows_with_price=1000,
            trading_rows=990,
            suspended_or_no_trade_rows=10,
            missing_count=0,
            coverage_ratio=1.0,
            duplicate_count=0,
            latest_date=target_date,
            status=AuditStatus.COMPLETE,
        ),
        tpex_daily=DailyPriceMarketAudit(
            market="TPEX",
            active_common_stocks=800,
            expected_eligible=800,
            rows_with_price=800,
            trading_rows=790,
            suspended_or_no_trade_rows=10,
            missing_count=0,
            coverage_ratio=1.0,
            duplicate_count=0,
            latest_date=target_date,
            status=AuditStatus.COMPLETE,
        ),
        market_spot=MarketSpotAudit(
            market_breadth_rows=2,
            margin_trading_rows=2,
            securities_lending_rows=1,
            institutional_spot_rows=2,
            duplicate_count=0,
            status=AuditStatus.COMPLETE,
        ),
        derivatives=[
            DerivativesDatasetAudit("TAIFEX_FUTURES_DAILY", 10, AuditStatus.COMPLETE),
            DerivativesDatasetAudit("OPTION_PUT_CALL_RATIO", 1, AuditStatus.COMPLETE),
            # VIX is known UNAVAILABLE
            DerivativesDatasetAudit(
                "VOLATILITY_INDEX", 0, AuditStatus.UNAVAILABLE, note="VIX unavailable"
            ),
        ],
        technicals=TechnicalsAudit(
            active_stocks=1800,
            snapshot_date=target_date,
            snapshots_count=1800,
            stale_count=0,
            ma240_eligible_count=1600,
            ma240_valid_count=1600,
            ma240_missing_count=0,
            duplicate_count=0,
            status=AuditStatus.COMPLETE,
        ),
        industry_strength=IndustryStrengthAudit(
            snapshot_date=target_date,
            snapshot_count=30,
            status=AuditStatus.COMPLETE,
        ),
        duplicates=DuplicateAudit(
            duplicate_securities=0,
            duplicate_daily_prices=0,
            duplicate_technical_snapshots=0,
            duplicate_market_spot=0,
            duplicate_derivatives=0,
            status=AuditStatus.COMPLETE,
        ),
        overall_status=AuditStatus.COMPLETE,
    )


def _mock_session_with_records(
    existing_anomalies: list[DataQualityAnomalyModel] | None = None,
    failed_runs: list[IngestionRunModel] | None = None,
) -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    anomalies = existing_anomalies or []
    runs = failed_runs or []

    async def scalars_side_effect(stmt):
        mock_result = MagicMock()
        query_str = str(stmt).lower()
        if "data_quality_anomalies" in query_str:
            mock_result.all.return_value = list(anomalies)
        elif "ingestion_runs" in query_str:
            mock_result.all.return_value = list(runs)
        else:
            mock_result.all.return_value = []
        return mock_result

    session.scalars.side_effect = scalars_side_effect
    return session


# 1. Weekend date -> SILENT
@pytest.mark.asyncio
async def test_weekend_date_silent() -> None:
    session = _mock_session_with_records()
    cal = MockTradingCalendar()
    service = DataQualityMonitoringService(session, calendar=cal)

    # 2026-09-06 is Sunday
    res = await service.evaluate_date(date(2026, 9, 6))
    assert res.anomalies_detected == 0
    assert res.notifications_created == 0
    assert len(res.notifications) == 0


# 2. Trading holiday -> SILENT
@pytest.mark.asyncio
async def test_holiday_date_silent() -> None:
    holiday = date(2026, 10, 10)
    session = _mock_session_with_records()
    cal = MockTradingCalendar(non_trading_dates={holiday})
    service = DataQualityMonitoringService(session, calendar=cal)

    res = await service.evaluate_date(holiday)
    assert res.anomalies_detected == 0
    assert res.notifications_created == 0
    assert len(res.notifications) == 0


# 3. Clean trading day -> SILENT (zero notifications)
@pytest.mark.asyncio
async def test_clean_trading_day_silent() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = _build_clean_audit_report(target)

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 0
    assert res.notifications_created == 0
    assert res.anomalies_active == 0
    assert len(res.notifications) == 0


# 4. Known unavailable limitation (VIX) filtered out -> SILENT
@pytest.mark.asyncio
async def test_known_unavailable_vix_filtered() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.derivatives = [
        DerivativesDatasetAudit(
            "VOLATILITY_INDEX", 0, AuditStatus.UNAVAILABLE, note="External limitation"
        ),
        DerivativesDatasetAudit("TAIFEX_FUTURES_DAILY", 10, AuditStatus.COMPLETE),
    ]

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 0
    assert res.notifications_created == 0


# 5. TWSE daily prices PARTIAL -> creates notification
@pytest.mark.asyncio
async def test_twse_partial_emits_notification() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.twse_daily.status = AuditStatus.PARTIAL
    report.twse_daily.coverage_ratio = 0.95
    report.twse_daily.missing_count = 50

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 1
    assert res.anomalies_new == 1
    assert res.notifications_created == 1
    notification = res.notifications[0]
    assert notification.dataset == "TWSE_DAILY"
    assert notification.anomaly_type == AnomalyType.DATASET_PARTIAL.value
    assert notification.dedupe_key == f"DATASET_PARTIAL|TWSE_DAILY|TWSE|{target.isoformat()}"


# 6. TPEX daily prices FAILED -> creates ERROR notification
@pytest.mark.asyncio
async def test_tpex_failed_emits_notification() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.tpex_daily.status = AuditStatus.FAILED
    report.tpex_daily.coverage_ratio = 0.50

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 1
    assert res.notifications[0].severity == AnomalySeverity.ERROR
    assert res.notifications[0].dataset == "TPEX_DAILY"


# 7. Ingestion run failed -> creates INGESTION_RUN_FAILED notification
@pytest.mark.asyncio
async def test_failed_ingestion_run_detected() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)

    failed_run = IngestionRunModel(
        id=uuid4(),
        provider="TWSE",
        dataset="DAILY_PRICES",
        started_at=now,
        finished_at=now + timedelta(seconds=10),
        status="FAILED",
        error_message="HTTP 502 Bad Gateway from TWSE exchange",
    )
    session = _mock_session_with_records(failed_runs=[failed_run])
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target, now=now)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 1
    assert res.notifications[0].anomaly_type == AnomalyType.INGESTION_RUN_FAILED.value
    assert "HTTP 502" in res.notifications[0].body


# 8. Duplicate records detected -> creates DUPLICATE_RECORDS notification
@pytest.mark.asyncio
async def test_duplicate_records_anomaly() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.duplicates.status = AuditStatus.FAILED
    report.duplicates.duplicate_daily_prices = 5

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 1
    assert res.notifications[0].anomaly_type == AnomalyType.DUPLICATE_RECORDS.value


# 9. Technicals stale -> creates DATASET_STALE notification
@pytest.mark.asyncio
async def test_technicals_stale_notification() -> None:
    target = date(2026, 9, 4)
    session = _mock_session_with_records()
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.technicals.status = AuditStatus.STALE
    report.technicals.stale_count = 1800
    report.technicals.snapshot_date = date(2026, 9, 3)

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target)

    assert res.anomalies_detected == 1
    assert res.notifications[0].anomaly_type == AnomalyType.DATASET_STALE.value


# 10. Repeated anomaly inside cooldown window -> SUPPRESSED
@pytest.mark.asyncio
async def test_repeated_anomaly_in_cooldown_is_suppressed() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)
    last_notified = now - timedelta(hours=2)

    dedupe_key = f"DATASET_PARTIAL|TWSE_DAILY|TWSE|{target.isoformat()}"
    existing = DataQualityAnomalyModel(
        id=uuid4(),
        dedupe_key=dedupe_key,
        anomaly_type=AnomalyType.DATASET_PARTIAL.value,
        dataset="TWSE_DAILY",
        scope_key="TWSE",
        target_date=target,
        severity=AnomalySeverity.WARNING.value,
        status=AnomalyStatus.ACTIVE.value,
        occurrence_count=1,
        first_seen_at=last_notified,
        last_seen_at=last_notified,
        last_notified_at=last_notified,
        resolved_at=None,
        message="TWSE partial",
        details={},
    )

    session = _mock_session_with_records(existing_anomalies=[existing])
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.twse_daily.status = AuditStatus.PARTIAL

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(
        session, calendar=cal, audit_service=audit_mock, cooldown_hours=24
    )
    res = await service.evaluate_date(target, now=now)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 0
    assert res.notifications_suppressed == 1
    assert existing.occurrence_count == 2


# 11. Repeated anomaly after cooldown window -> NOTIFIED
@pytest.mark.asyncio
async def test_repeated_anomaly_after_cooldown_is_notified() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)
    last_notified = now - timedelta(hours=25)

    dedupe_key = f"DATASET_PARTIAL|TWSE_DAILY|TWSE|{target.isoformat()}"
    existing = DataQualityAnomalyModel(
        id=uuid4(),
        dedupe_key=dedupe_key,
        anomaly_type=AnomalyType.DATASET_PARTIAL.value,
        dataset="TWSE_DAILY",
        scope_key="TWSE",
        target_date=target,
        severity=AnomalySeverity.WARNING.value,
        status=AnomalyStatus.ACTIVE.value,
        occurrence_count=1,
        first_seen_at=last_notified,
        last_seen_at=last_notified,
        last_notified_at=last_notified,
        resolved_at=None,
        message="TWSE partial",
        details={},
    )

    session = _mock_session_with_records(existing_anomalies=[existing])
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.twse_daily.status = AuditStatus.PARTIAL

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(
        session, calendar=cal, audit_service=audit_mock, cooldown_hours=24
    )
    res = await service.evaluate_date(target, now=now)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 1
    assert res.notifications_suppressed == 0
    assert existing.occurrence_count == 2
    assert existing.last_notified_at == now


# 12. Severity escalation inside cooldown -> NOTIFIED IMMEDIATELY
@pytest.mark.asyncio
async def test_severity_escalation_bypasses_cooldown() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)
    last_notified = now - timedelta(minutes=30)

    dedupe_key = f"DATASET_FAILED|TWSE_DAILY|TWSE|{target.isoformat()}"
    existing = DataQualityAnomalyModel(
        id=uuid4(),
        dedupe_key=dedupe_key,
        anomaly_type=AnomalyType.DATASET_FAILED.value,
        dataset="TWSE_DAILY",
        scope_key="TWSE",
        target_date=target,
        severity=AnomalySeverity.WARNING.value,
        status=AnomalyStatus.ACTIVE.value,
        occurrence_count=1,
        first_seen_at=last_notified,
        last_seen_at=last_notified,
        last_notified_at=last_notified,
        resolved_at=None,
        message="TWSE initial partial",
        details={},
    )

    session = _mock_session_with_records(existing_anomalies=[existing])
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.twse_daily.status = AuditStatus.FAILED

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(
        session, calendar=cal, audit_service=audit_mock, cooldown_hours=24
    )
    res = await service.evaluate_date(target, now=now)

    assert res.notifications_created == 1
    assert res.notifications_suppressed == 0
    assert "【異常升級】" in res.notifications[0].title
    assert existing.severity == AnomalySeverity.ERROR.value


# 13. Previously active anomaly now healed -> RESOLUTION notification
@pytest.mark.asyncio
async def test_resolved_anomaly_emits_resolution_notification() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)

    dedupe_key = f"DATASET_PARTIAL|TWSE_DAILY|TWSE|{target.isoformat()}"
    existing = DataQualityAnomalyModel(
        id=uuid4(),
        dedupe_key=dedupe_key,
        anomaly_type=AnomalyType.DATASET_PARTIAL.value,
        dataset="TWSE_DAILY",
        scope_key="TWSE",
        target_date=target,
        severity=AnomalySeverity.WARNING.value,
        status=AnomalyStatus.ACTIVE.value,
        occurrence_count=1,
        first_seen_at=now - timedelta(hours=5),
        last_seen_at=now - timedelta(hours=5),
        last_notified_at=now - timedelta(hours=5),
        resolved_at=None,
        message="TWSE partial",
        details={},
    )

    session = _mock_session_with_records(existing_anomalies=[existing])
    cal = MockTradingCalendar()

    clean_report = _build_clean_audit_report(target)
    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = clean_report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target, now=now)

    assert res.anomalies_detected == 0
    assert res.anomalies_resolved == 1
    assert res.notifications_created == 1
    notif = res.notifications[0]
    assert notif.is_resolution is True
    assert "【資料異常已修復】" in notif.title
    assert existing.status == AnomalyStatus.RESOLVED.value
    assert existing.resolved_at == now


# 14. Reoccurrence of previously resolved anomaly -> NEW EPISODE
@pytest.mark.asyncio
async def test_reoccurrence_reactivates_resolved_anomaly() -> None:
    target = date(2026, 9, 4)
    now = datetime(2026, 9, 4, 18, 0, 0, tzinfo=UTC)

    dedupe_key = f"DATASET_PARTIAL|TWSE_DAILY|TWSE|{target.isoformat()}"
    resolved_record = DataQualityAnomalyModel(
        id=uuid4(),
        dedupe_key=dedupe_key,
        anomaly_type=AnomalyType.DATASET_PARTIAL.value,
        dataset="TWSE_DAILY",
        scope_key="TWSE",
        target_date=target,
        severity=AnomalySeverity.WARNING.value,
        status=AnomalyStatus.RESOLVED.value,
        occurrence_count=2,
        first_seen_at=now - timedelta(days=2),
        last_seen_at=now - timedelta(days=1),
        last_notified_at=now - timedelta(days=2),
        resolved_at=now - timedelta(days=1),
        message="TWSE partial",
        details={},
    )

    session = _mock_session_with_records(existing_anomalies=[resolved_record])
    cal = MockTradingCalendar()

    report = _build_clean_audit_report(target)
    report.twse_daily.status = AuditStatus.PARTIAL

    audit_mock = AsyncMock()
    audit_mock.audit_date.return_value = report

    service = DataQualityMonitoringService(session, calendar=cal, audit_service=audit_mock)
    res = await service.evaluate_date(target, now=now)

    assert res.anomalies_detected == 1
    assert res.notifications_created == 1
    assert resolved_record.status == AnomalyStatus.ACTIVE.value
    assert resolved_record.resolved_at is None
    assert resolved_record.occurrence_count == 3


# 15. CLI human print smoke test
def test_cli_human_output_smoke() -> None:
    res = MonitoringRunResult(
        target_date=date(2026, 9, 4),
        anomalies_detected=2,
        anomalies_active=2,
        anomalies_new=1,
        anomalies_resolved=1,
        notifications_created=2,
        notifications_suppressed=1,
        notifications=[
            NotificationEvent(
                event_id=uuid4(),
                anomaly_type=AnomalyType.DATASET_PARTIAL.value,
                severity=AnomalySeverity.WARNING,
                dedupe_key="DATASET_PARTIAL|TWSE_DAILY|TWSE|2026-09-04",
                title="【資料異常警示】TWSE_DAILY DATASET_PARTIAL",
                body="Coverage partial",
                target_date=date(2026, 9, 4),
                dataset="TWSE_DAILY",
                created_at=datetime.now(UTC),
                occurrence_count=1,
            ),
            NotificationEvent(
                event_id=uuid4(),
                anomaly_type=AnomalyType.DATASET_FAILED.value,
                severity=AnomalySeverity.INFO,
                dedupe_key="DATASET_FAILED|TPEX_DAILY|TPEX|2026-09-04",
                title="【資料異常已修復】TPEX_DAILY DATASET_FAILED",
                body="Resolved",
                target_date=date(2026, 9, 4),
                dataset="TPEX_DAILY",
                created_at=datetime.now(UTC),
                occurrence_count=2,
                is_resolution=True,
            ),
        ],
    )
    print_human_monitoring_result(res)
