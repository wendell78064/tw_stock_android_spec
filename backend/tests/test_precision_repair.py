from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cli.repair_market_data import print_human_repair_result
from app.core.job_lock import distributed_job_lock
from app.domain.audit import (
    MAX_REPAIR_RANGE_DAYS,
    AuditFinding,
    AuditStatus,
    PrecisionRepairResult,
    RepairDecision,
    RepairDecisionOutcome,
    RepairScope,
    RepairScopeType,
)
from app.services.precision_repair import PrecisionRepairPlanner, PrecisionRepairService


class MockTradingCalendar:
    def __init__(self, holidays: set[date] | None = None):
        self.holidays = holidays or set()

    def is_trading_day(self, value: date) -> bool:
        if value in self.holidays:
            return False
        return value.weekday() < 5

    def previous_trading_day(self, value: date) -> date:
        return value


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    async def eval(self, script, numkeys, key, token):
        if self.data.get(key) == token:
            del self.data[key]
            return 1
        return 0


# 1. Holiday -> no repair
def test_planner_holiday_no_repair() -> None:
    cal = MockTradingCalendar(holidays={date(2026, 4, 6)})
    planner = PrecisionRepairPlanner(cal)

    finding = AuditFinding(
        finding_id="f-holiday",
        dataset="DAILY_PRICES",
        target_date=date(2026, 4, 6),
        audit_status=AuditStatus.NO_DATA,
        reason="Missing prices on holiday",
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.HOLIDAY
    assert decision.scope is None
    assert "non-trading day" in decision.reason


# Weekend -> holiday outcome
def test_planner_weekend_no_repair() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-weekend",
        dataset="TWSE_DAILY",
        target_date=date(2026, 8, 8),  # Saturday
        audit_status=AuditStatus.NO_DATA,
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.HOLIDAY


# 2. Future date -> not published
def test_planner_future_date_not_published() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-future",
        dataset="DAILY_PRICES",
        target_date=date(2099, 1, 1),
        audit_status=AuditStatus.NO_DATA,
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.NOT_PUBLISHED
    assert decision.scope is None


# 3. Same-day not-yet-published -> NOT_PUBLISHED
def test_planner_same_day_not_yet_published() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    today = date.today()
    finding = AuditFinding(
        finding_id="f-today-upstream",
        dataset="TAIFEX_PUT_CALL",
        target_date=today,
        audit_status=AuditStatus.NO_DATA,
        reason="TAIFEX upstream publication pending",
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.NOT_PUBLISHED
    assert decision.scope is None
    assert "not yet published upstream" in decision.reason


# 4. Unavailable capability -> no repair (VIX)
def test_planner_vix_unavailable_no_repair() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-vix",
        dataset="VOLATILITY_INDEX",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.UNAVAILABLE,
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.UNAVAILABLE
    assert decision.scope is None
    assert "Taiwan VIX is unavailable" in decision.reason


# 5. Status COMPLETE -> SKIP
def test_planner_already_complete_skip() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-comp",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.COMPLETE,
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.SKIP


# 6. Unsupported dataset -> UNSUPPORTED
def test_planner_unsupported_dataset() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-unknown",
        dataset="RANDOM_UNKNOWN_FEED",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.UNSUPPORTED


# 7. One missing security -> exact security repair scope
def test_planner_one_missing_security_exact_scope() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-sec-2330",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        market="TWSE",
        security_code="2330",
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.REPAIRABLE
    assert decision.scope is not None
    assert decision.scope.scope_type == RepairScopeType.SECURITY_DATE
    assert decision.scope.market == "TWSE"
    assert decision.scope.security_code == "2330"
    assert decision.scope.target_date == date(2026, 8, 7)


# 8. One missing date -> exact dataset date repair scope
def test_planner_one_missing_date_exact_scope() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-date-twse",
        dataset="TWSE_DAILY",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        market="TWSE",
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.REPAIRABLE
    assert decision.scope is not None
    assert decision.scope.scope_type == RepairScopeType.DATASET_DATE
    assert decision.scope.target_date == date(2026, 8, 7)
    assert decision.scope.security_code is None


# 9. Date range -> valid bounded date range scope accepted
def test_planner_valid_bounded_date_range_scope() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-range-valid",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        start_date=date(2026, 8, 3),
        end_date=date(2026, 8, 7),
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.REPAIRABLE
    assert decision.scope is not None
    assert decision.scope.scope_type == RepairScopeType.DATE_RANGE
    assert decision.scope.start_date == date(2026, 8, 3)
    assert decision.scope.end_date == date(2026, 8, 7)


# 10. Multi-year DATE_RANGE -> rejected as UNSUPPORTED / exceeds MAX_REPAIR_RANGE_DAYS
def test_planner_multi_year_range_rejected() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-multiyear",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        start_date=date(2021, 1, 1),
        end_date=date(2026, 8, 7),  # > 5 years
    )
    decision = planner.plan_repair(finding)
    assert decision.outcome == RepairDecisionOutcome.UNSUPPORTED
    assert decision.scope is None
    expected_msg = f"exceeds maximum allowed precision repair limit ({MAX_REPAIR_RANGE_DAYS} days)"
    assert expected_msg in decision.reason

    # RepairScope constructor directly raises ValueError
    with pytest.raises(ValueError, match="exceeds maximum allowed precision repair limit"):
        RepairScope(
            scope_type=RepairScopeType.DATE_RANGE,
            dataset="DAILY_PRICES",
            start_date=date(2021, 1, 1),
            end_date=date(2026, 8, 7),
        )


# 11. Execution: Non-repairable returns unexecuted result with same status (no mutation)
@pytest.mark.asyncio
async def test_service_execute_holiday_unexecuted() -> None:
    cal = MockTradingCalendar(holidays={date(2026, 4, 6)})
    mock_session = AsyncMock()
    service = PrecisionRepairService(mock_session, cal)

    finding = AuditFinding(
        finding_id="f-hol",
        dataset="DAILY_PRICES",
        target_date=date(2026, 4, 6),
        audit_status=AuditStatus.NO_DATA,
    )
    result = await service.execute_repair(finding)
    assert not result.executed
    assert result.decision.outcome == RepairDecisionOutcome.HOLIDAY
    assert result.status_before == AuditStatus.NO_DATA
    assert result.status_after == AuditStatus.NO_DATA


# 12. Execution: Successful repair -> re-audit PASS / COMPLETE + audit trail persisted
@pytest.mark.asyncio
async def test_service_execute_successful_repair_and_reaudit_and_persisted() -> None:
    cal = MockTradingCalendar()
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.get.return_value = None  # creates new IngestionRunModel
    service = PrecisionRepairService(mock_session, cal, provider_mode="fake")

    # Mock dispatch and re-audit
    service._dispatch_repair = AsyncMock(return_value=(10, 0, "run-12345"))
    service._re_audit_scope = AsyncMock(
        return_value=(AuditStatus.COMPLETE, {"status": "COMPLETE", "rows": 10})
    )

    finding = AuditFinding(
        finding_id="f-succ",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        market="TWSE",
        security_code="2330",
    )
    result = await service.execute_repair(finding)
    assert result.executed
    assert result.status_before == AuditStatus.PARTIAL
    assert result.status_after == AuditStatus.COMPLETE
    assert result.repaired_records_inserted == 10
    assert result.ingestion_run_id is not None
    assert result.re_audit_report["status"] == "COMPLETE"
    # Ensure session committed audit trail model
    assert mock_session.add.called
    assert mock_session.commit.called


# 13. Execution: Failed repair -> truthful FAILED/PARTIAL status retained
@pytest.mark.asyncio
async def test_service_execute_failed_repair_truthful_status() -> None:
    cal = MockTradingCalendar()
    mock_session = AsyncMock()
    service = PrecisionRepairService(mock_session, cal, provider_mode="fake")

    service._dispatch_repair = AsyncMock(side_effect=RuntimeError("Provider connection reset"))
    service._re_audit_scope = AsyncMock(
        return_value=(AuditStatus.FAILED, {"status": "FAILED", "reason": "Repair execution failed"})
    )

    finding = AuditFinding(
        finding_id="f-fail",
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        audit_status=AuditStatus.PARTIAL,
        market="TWSE",
    )
    result = await service.execute_repair(finding)
    assert not result.executed
    assert "Provider connection reset" in (result.error or "")
    assert result.status_after == AuditStatus.FAILED


# 14. Concurrency: Daily Pipeline and Precision Repair share "daily-pipeline" lock key
@pytest.mark.asyncio
async def test_daily_pipeline_active_blocks_precision_repair() -> None:
    fake_redis = FakeRedis()
    mock_session = AsyncMock()
    cal = MockTradingCalendar()

    # Daily pipeline acquires the lock
    async with distributed_job_lock(fake_redis, "daily-pipeline") as acquired:
        assert acquired is True

        # While daily pipeline holds lock, precision repair attempts to execute
        service = PrecisionRepairService(mock_session, cal, redis=fake_redis)
        finding = AuditFinding(
            finding_id="f-lock-test",
            dataset="DAILY_PRICES",
            target_date=date(2026, 8, 7),
            audit_status=AuditStatus.PARTIAL,
            market="TWSE",
            security_code="2330",
        )
        result = await service.execute_repair(finding)
        assert not result.executed
        assert "JOB_LOCK_BUSY" in (result.error or "")


# 15. Concurrency: Precision Repair active blocks Daily Pipeline
@pytest.mark.asyncio
async def test_precision_repair_active_blocks_daily_pipeline() -> None:
    fake_redis = FakeRedis()

    # Acquire lock as Precision Repair does (key: daily-pipeline)
    async with distributed_job_lock(fake_redis, "daily-pipeline") as repair_lock:
        assert repair_lock is True

        # Now daily pipeline attempts to acquire the same lock
        async with distributed_job_lock(fake_redis, "daily-pipeline") as pipeline_lock:
            assert pipeline_lock is False  # Mutually excluded!

    # Safe release: after context exit, lock is free again
    async with distributed_job_lock(fake_redis, "daily-pipeline") as final_lock:
        assert final_lock is True


# 16. SECURITY_DATE re-audit checks real validity (invalid OHLC is rejected as FAILED)
@pytest.mark.asyncio
async def test_security_date_reaudit_checks_real_data_quality() -> None:
    cal = MockTradingCalendar()
    mock_session = AsyncMock()
    service = PrecisionRepairService(mock_session, cal)

    # Mock DB row with inverted high/low (high < low)
    class MockRow:
        open = 100.0
        high = 90.0   # invalid: high < open
        low = 80.0
        close = 95.0
        volume_shares = 1000

    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = MockRow()
    mock_session.execute.return_value = mock_res

    scope = RepairScope(
        scope_type=RepairScopeType.SECURITY_DATE,
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        market="TWSE",
        security_code="2330",
    )
    status, report = await service._re_audit_scope(scope)
    assert status == AuditStatus.FAILED
    assert "INVALID_OHLC" in report["reason"]


# 17. Human print output executes cleanly
def test_print_human_repair_result(capsys) -> None:
    scope = RepairScope(
        scope_type=RepairScopeType.SECURITY_DATE,
        dataset="DAILY_PRICES",
        target_date=date(2026, 8, 7),
        market="TWSE",
        security_code="2330",
    )
    dec = RepairDecision(
        finding_id="f-test",
        outcome=RepairDecisionOutcome.REPAIRABLE,
        reason="Missing price row",
        scope=scope,
    )
    res = PrecisionRepairResult(
        finding_id="f-test",
        decision=dec,
        executed=True,
        status_before=AuditStatus.PARTIAL,
        status_after=AuditStatus.COMPLETE,
        repaired_records_inserted=1,
        repaired_records_updated=0,
        ingestion_run_id="run-uuid-1234",
    )
    print_human_repair_result(res)
    out = capsys.readouterr().out
    assert "PRECISION MARKET DATA REPAIR REPORT" in out
    assert "REPAIRABLE" in out
    assert "SECURITY_DATE" in out
    assert "Status After:    COMPLETE" in out
