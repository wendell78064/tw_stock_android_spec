from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.domain.audit import (
    AuditStatus,
    DailyDataAuditReport,
)
from app.domain.calendar import TradingCalendar
from app.domain.monitoring import (
    AnomalyEvent,
    AnomalySeverity,
    AnomalyStatus,
    AnomalyType,
    MonitoringRunResult,
    NotificationEvent,
)
from app.repositories.models import DataQualityAnomalyModel, IngestionRunModel
from app.services.data_quality_audit import DataQualityAuditService

# Default cooldown period: 24 hours between duplicate notifications unless severity escalates
DEFAULT_COOLDOWN_HOURS: int = 24


class DataQualityMonitoringService:
    def __init__(
        self,
        session: AsyncSession,
        calendar: TradingCalendar | None = None,
        audit_service: DataQualityAuditService | None = None,
        cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
    ):
        self.session = session
        self.calendar = calendar or WeekendOnlyCalendar()
        self.audit_service = audit_service or DataQualityAuditService(session, self.calendar)
        self.cooldown_delta = timedelta(hours=cooldown_hours)

    async def evaluate_date(
        self,
        target_date: date,
        now: datetime | None = None,
    ) -> MonitoringRunResult:
        """Evaluates data quality for target_date and determines anomaly notifications.

        Guarantees:
        - Non-trading days (weekends/holidays) are completely silent.
        - COMPLETE / NORMAL audit reports generate ZERO notifications.
        - Known external limitations (e.g. TAIFEX VIX) are filtered and produce zero noise.
        - True anomalies (PARTIAL, FAILED, excessive STALE, ingestion exceptions) generate
          stable deduplicated notifications subject to cooldown.
        - Previously active anomalies that are resolved generate a resolution notification.
        """
        now_utc = now or datetime.now(UTC)

        # 1. Trading Calendar check: Non-trading days are silent by definition
        if not self.calendar.is_trading_day(target_date):
            return MonitoringRunResult(
                target_date=target_date,
                anomalies_detected=0,
                anomalies_active=0,
                anomalies_new=0,
                anomalies_resolved=0,
                notifications_created=0,
                notifications_suppressed=0,
                notifications=[],
            )

        # 2. Run Audit for target_date
        report: DailyDataAuditReport = await self.audit_service.audit_date(target_date)

        # 3. Check Ingestion Runs for target_date
        ingestion_runs_failed = await self._check_failed_ingestion_runs(target_date)

        # 4. Extract Anomaly Events from Audit & Ingestion Runs
        detected_anomalies = self._extract_anomalies(report, ingestion_runs_failed)

        # If no anomalies detected and overall is COMPLETE/NORMAL
        detected_dedupe_keys = {a.dedupe_key: a for a in detected_anomalies}

        # 5. Load existing anomaly records for target_date from DB
        stmt = select(DataQualityAnomalyModel).where(
            DataQualityAnomalyModel.target_date == target_date
        )
        existing_records: list[DataQualityAnomalyModel] = (
            (await self.session.scalars(stmt)).all()
        )
        existing_by_key: dict[str, DataQualityAnomalyModel] = {
            r.dedupe_key: r for r in existing_records
        }

        notifications: list[NotificationEvent] = []
        new_anomalies_count = 0
        suppressed_count = 0
        resolved_count = 0

        # 6. Process Detected Anomalies
        for dedupe_key, anomaly in detected_dedupe_keys.items():
            record = existing_by_key.get(dedupe_key)
            if record is None:
                # NEW Anomaly
                new_record = DataQualityAnomalyModel(
                    id=uuid4(),
                    dedupe_key=dedupe_key,
                    anomaly_type=anomaly.anomaly_type.value,
                    dataset=anomaly.dataset,
                    scope_key=anomaly.scope_key,
                    target_date=anomaly.target_date,
                    severity=anomaly.severity.value,
                    status=AnomalyStatus.ACTIVE.value,
                    occurrence_count=1,
                    first_seen_at=now_utc,
                    last_seen_at=now_utc,
                    last_notified_at=now_utc,
                    resolved_at=None,
                    message=anomaly.message,
                    details=anomaly.details,
                )
                self.session.add(new_record)
                new_anomalies_count += 1

                body_msg = (
                    f"日期: {anomaly.target_date.isoformat()} | "
                    f"範圍: {anomaly.scope_key} | 詳情: {anomaly.message}"
                )
                notifications.append(
                    NotificationEvent(
                        event_id=uuid4(),
                        anomaly_type=anomaly.anomaly_type.value,
                        severity=anomaly.severity,
                        dedupe_key=dedupe_key,
                        title=f"【資料異常通知】{anomaly.dataset} {anomaly.anomaly_type.value}",
                        body=body_msg,
                        target_date=anomaly.target_date,
                        dataset=anomaly.dataset,
                        created_at=now_utc,
                        occurrence_count=1,
                        is_resolution=False,
                        details=anomaly.details,
                    )
                )
            else:
                # EXISTING Anomaly
                record.last_seen_at = now_utc
                record.occurrence_count += 1
                record.message = anomaly.message
                record.details = anomaly.details

                # Re-activate if was resolved (new episode of recurring issue)
                was_resolved = record.status == AnomalyStatus.RESOLVED.value
                if was_resolved:
                    record.status = AnomalyStatus.ACTIVE.value
                    record.resolved_at = None

                # Check cooldown and severity escalation
                severity_order = {
                    AnomalySeverity.INFO.value: 1,
                    AnomalySeverity.WARNING.value: 2,
                    AnomalySeverity.ERROR.value: 3,
                    AnomalySeverity.CRITICAL.value: 4,
                }
                prev_sev_rank = severity_order.get(record.severity, 1)
                curr_sev_rank = severity_order.get(anomaly.severity.value, 1)
                severity_escalated = curr_sev_rank > prev_sev_rank

                in_cooldown = (
                    record.last_notified_at is not None
                    and (now_utc - record.last_notified_at) < self.cooldown_delta
                )

                if was_resolved or severity_escalated or not in_cooldown:
                    record.severity = anomaly.severity.value
                    record.last_notified_at = now_utc

                    title_prefix = "【異常升級】" if severity_escalated else "【資料異常警示】"
                    body_msg = (
                        f"日期: {anomaly.target_date.isoformat()} | 範圍: {anomaly.scope_key} | "
                        f"次數: {record.occurrence_count} | 詳情: {anomaly.message}"
                    )
                    notifications.append(
                        NotificationEvent(
                            event_id=uuid4(),
                            anomaly_type=anomaly.anomaly_type.value,
                            severity=anomaly.severity,
                            dedupe_key=dedupe_key,
                            title=f"{title_prefix}{anomaly.dataset} {anomaly.anomaly_type.value}",
                            body=body_msg,
                            target_date=anomaly.target_date,
                            dataset=anomaly.dataset,
                            created_at=now_utc,
                            occurrence_count=record.occurrence_count,
                            is_resolution=False,
                            details=anomaly.details,
                        )
                    )
                else:
                    suppressed_count += 1

        # 7. Check for Resolution: active records in DB that are NO LONGER detected
        for dedupe_key, record in existing_by_key.items():
            if (
                record.status == AnomalyStatus.ACTIVE.value
                and dedupe_key not in detected_dedupe_keys
            ):
                # Mark as RESOLVED
                record.status = AnomalyStatus.RESOLVED.value
                record.resolved_at = now_utc
                resolved_count += 1

                body_msg = (
                    f"日期: {record.target_date.isoformat()} | 範圍: {record.scope_key} | "
                    f"先前記綠已確認修復恢復正常。"
                )
                notifications.append(
                    NotificationEvent(
                        event_id=uuid4(),
                        anomaly_type=record.anomaly_type,
                        severity=AnomalySeverity.INFO,
                        dedupe_key=dedupe_key,
                        title=f"【資料異常已修復】{record.dataset} {record.anomaly_type}",
                        body=body_msg,
                        target_date=record.target_date,
                        dataset=record.dataset,
                        created_at=now_utc,
                        occurrence_count=record.occurrence_count,
                        is_resolution=True,
                        details={"resolved_from_dedupe_key": dedupe_key},
                    )
                )

        await self.session.commit()

        active_count = len(detected_dedupe_keys)

        return MonitoringRunResult(
            target_date=target_date,
            anomalies_detected=len(detected_anomalies),
            anomalies_active=active_count,
            anomalies_new=new_anomalies_count,
            anomalies_resolved=resolved_count,
            notifications_created=len(notifications),
            notifications_suppressed=suppressed_count,
            notifications=notifications,
        )

    async def _check_failed_ingestion_runs(self, target_date: date) -> list[IngestionRunModel]:
        day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        day_end = datetime.combine(
            target_date + timedelta(days=1), datetime.min.time(), tzinfo=UTC
        )
        stmt = (
            select(IngestionRunModel)
            .where(
                IngestionRunModel.started_at >= day_start,
                IngestionRunModel.started_at < day_end,
                IngestionRunModel.status.in_(["FAILED", "ERROR"]),
            )
        )
        return list((await self.session.scalars(stmt)).all())

    def _extract_anomalies(
        self,
        report: DailyDataAuditReport,
        failed_runs: list[IngestionRunModel],
    ) -> list[AnomalyEvent]:
        anomalies: list[AnomalyEvent] = []

        # If day is non-trading or holiday, no anomalies
        if report.day_type in ("WEEKEND", "HOLIDAY") or not report.is_trading_day:
            return []

        # 1. Ingestion runs failure check
        for run in failed_runs:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.INGESTION_RUN_FAILED,
                    dataset=run.dataset,
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key=run.provider or "PROVIDER",
                    message=f"Ingestion run failed: {run.error_message or 'Unknown error'}",
                    details={
                        "run_id": str(run.id),
                        "provider": run.provider,
                        "error_message": run.error_message,
                    },
                )
            )

        # 2. Security master audit
        sec = report.security_master
        if sec.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="SECURITY_MASTER",
                    target_date=report.target_date,
                    severity=AnomalySeverity.CRITICAL,
                    scope_key="GLOBAL",
                    message=f"Security master audit failed (duplicates={sec.duplicate_count})",
                    details={"duplicate_count": sec.duplicate_count},
                )
            )
        elif sec.status == AuditStatus.PARTIAL:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="SECURITY_MASTER",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="GLOBAL",
                    message=f"Security master incomplete: active={sec.active_common_stocks}",
                    details={"active_common_stocks": sec.active_common_stocks},
                )
            )

        # 3. TWSE Daily Prices
        twse = report.twse_daily
        cov_twse = f"{twse.coverage_ratio * 100:.1f}%"
        if twse.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="TWSE_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="TWSE",
                    message=f"TWSE daily failed: cov={cov_twse}, missing={twse.missing_count}",
                    details={
                        "missing_count": twse.missing_count,
                        "coverage_ratio": twse.coverage_ratio,
                    },
                )
            )
        elif twse.status == AuditStatus.PARTIAL:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="TWSE_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="TWSE",
                    message=f"TWSE daily partial: cov={cov_twse}, missing={twse.missing_count}",
                    details={
                        "missing_count": twse.missing_count,
                        "coverage_ratio": twse.coverage_ratio,
                    },
                )
            )
        elif twse.status == AuditStatus.NO_DATA:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_NO_DATA,
                    dataset="TWSE_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="TWSE",
                    message="TWSE daily prices has no data on trading day",
                    details={},
                )
            )

        # 4. TPEX Daily Prices
        tpex = report.tpex_daily
        cov_tpex = f"{tpex.coverage_ratio * 100:.1f}%"
        if tpex.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="TPEX_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="TPEX",
                    message=f"TPEX daily failed: cov={cov_tpex}, missing={tpex.missing_count}",
                    details={
                        "missing_count": tpex.missing_count,
                        "coverage_ratio": tpex.coverage_ratio,
                    },
                )
            )
        elif tpex.status == AuditStatus.PARTIAL:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="TPEX_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="TPEX",
                    message=f"TPEX daily partial: cov={cov_tpex}, missing={tpex.missing_count}",
                    details={
                        "missing_count": tpex.missing_count,
                        "coverage_ratio": tpex.coverage_ratio,
                    },
                )
            )
        elif tpex.status == AuditStatus.NO_DATA:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_NO_DATA,
                    dataset="TPEX_DAILY",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="TPEX",
                    message="TPEX daily prices has no data on trading day",
                    details={},
                )
            )

        # 5. Market Spot
        spot = report.market_spot
        if spot.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="MARKET_SPOT",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="GLOBAL",
                    message=f"Market spot check failed (duplicates={spot.duplicate_count})",
                    details={"duplicates": spot.duplicate_count},
                )
            )
        elif spot.status == AuditStatus.PARTIAL:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="MARKET_SPOT",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="GLOBAL",
                    message="Market spot missing sub-dataset feeds",
                    details={
                        "breadth": spot.market_breadth_rows,
                        "margin": spot.margin_trading_rows,
                        "lending": spot.securities_lending_rows,
                        "institutional": spot.institutional_spot_rows,
                    },
                )
            )

        # 6. Derivatives (filter out UNAVAILABLE e.g. VOLATILITY_INDEX / VIX)
        for d in report.derivatives:
            if d.dataset.upper() in ("VOLATILITY_INDEX", "TAIFEX_VIX", "VIX"):
                continue
            if d.status == AuditStatus.UNAVAILABLE:
                continue

            if d.status == AuditStatus.FAILED:
                anomalies.append(
                    AnomalyEvent(
                        anomaly_type=AnomalyType.DATASET_FAILED,
                        dataset=d.dataset,
                        target_date=report.target_date,
                        severity=AnomalySeverity.ERROR,
                        scope_key="TAIFEX",
                        message=f"Derivatives {d.dataset} failed: rows={d.row_count}",
                        details={"row_count": d.row_count, "note": d.note},
                    )
                )
            elif d.status in (AuditStatus.PARTIAL, AuditStatus.NO_DATA):
                anom_type = (
                    AnomalyType.DATASET_PARTIAL
                    if d.status == AuditStatus.PARTIAL
                    else AnomalyType.DATASET_NO_DATA
                )
                anomalies.append(
                    AnomalyEvent(
                        anomaly_type=anom_type,
                        dataset=d.dataset,
                        target_date=report.target_date,
                        severity=AnomalySeverity.WARNING,
                        scope_key="TAIFEX",
                        message=f"Derivatives {d.dataset} {d.status.value}: rows={d.row_count}",
                        details={"row_count": d.row_count, "note": d.note},
                    )
                )

        # 7. Technicals
        tech = report.technicals
        if tech.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="TECHNICALS",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="GLOBAL",
                    message=(
                        f"Technicals failed: ma240_missing={tech.ma240_missing_count}, "
                        f"dup={tech.duplicate_count}"
                    ),
                    details={
                        "ma240_missing_count": tech.ma240_missing_count,
                        "duplicate_count": tech.duplicate_count,
                    },
                )
            )
        elif tech.status == AuditStatus.STALE:
            snap_dt = str(tech.snapshot_date)
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_STALE,
                    dataset="TECHNICALS",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="GLOBAL",
                    message=f"Technicals stale: cnt={tech.stale_count} (as_of={snap_dt})",
                    details={
                        "stale_count": tech.stale_count,
                        "snapshot_date": snap_dt,
                    },
                )
            )
        elif tech.status == AuditStatus.PARTIAL:
            total_stk = tech.active_stocks
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="TECHNICALS",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="GLOBAL",
                    message=f"Technicals partial: snaps={tech.snapshots_count}/{total_stk}",
                    details={
                        "snapshots": tech.snapshots_count,
                        "active_stocks": tech.active_stocks,
                    },
                )
            )

        # 8. Industry Strength
        ind = report.industry_strength
        if ind.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_FAILED,
                    dataset="INDUSTRY_STRENGTH",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="GLOBAL",
                    message=f"Industry strength audit failed (count={ind.snapshot_count})",
                    details={"snapshot_count": ind.snapshot_count},
                )
            )
        elif ind.status in (AuditStatus.PARTIAL, AuditStatus.NO_DATA):
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DATASET_PARTIAL,
                    dataset="INDUSTRY_STRENGTH",
                    target_date=report.target_date,
                    severity=AnomalySeverity.WARNING,
                    scope_key="GLOBAL",
                    message=f"Industry strength missing snapshot: count={ind.snapshot_count}",
                    details={"snapshot_count": ind.snapshot_count},
                )
            )

        # 9. Duplicates
        dup = report.duplicates
        if dup.status == AuditStatus.FAILED:
            anomalies.append(
                AnomalyEvent(
                    anomaly_type=AnomalyType.DUPLICATE_RECORDS,
                    dataset="DATABASE",
                    target_date=report.target_date,
                    severity=AnomalySeverity.ERROR,
                    scope_key="GLOBAL",
                    message=(
                        f"Duplicates: sec={dup.duplicate_securities}, "
                        f"price={dup.duplicate_daily_prices}, "
                        f"tech={dup.duplicate_technical_snapshots}"
                    ),
                    details={
                        "duplicate_securities": dup.duplicate_securities,
                        "duplicate_daily_prices": dup.duplicate_daily_prices,
                        "duplicate_technical_snapshots": dup.duplicate_technical_snapshots,
                        "duplicate_market_spot": dup.duplicate_market_spot,
                        "duplicate_derivatives": dup.duplicate_derivatives,
                    },
                )
            )

        return anomalies
