from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.cli.repair_market_data import print_human_repair_result
from app.domain.audit import (
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


# 2. Not published -> no repair
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


# 3. Unavailable capability -> no repair (VIX)
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


# 4. Status COMPLETE -> SKIP
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


# 5. Unsupported dataset -> UNSUPPORTED
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


# 6. One missing security -> exact security repair scope
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


# 7. One missing date -> exact dataset date repair scope
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


# 8. Date range -> bounded date range scope
def test_planner_bounded_date_range_scope() -> None:
    planner = PrecisionRepairPlanner(MockTradingCalendar())
    finding = AuditFinding(
        finding_id="f-range",
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


# 9. Execution: Non-repairable returns unexecuted result with same status
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


# 10. Execution: Successful repair -> re-audit PASS / COMPLETE
@pytest.mark.asyncio
async def test_service_execute_successful_repair_and_reaudit() -> None:
    cal = MockTradingCalendar()
    mock_session = AsyncMock()
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
    assert result.ingestion_run_id == "run-12345"
    assert result.re_audit_report["status"] == "COMPLETE"


# 11. Execution: Failed repair -> truthful FAILED/PARTIAL status retained
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


# 12. Concurrency: Lock busy prevents concurrent mutation
@pytest.mark.asyncio
async def test_service_lock_busy_prevents_mutation() -> None:
    cal = MockTradingCalendar()
    mock_session = AsyncMock()
    mock_redis = AsyncMock()

    # simulate lock acquisition failure
    with patch("app.services.precision_repair.distributed_job_lock") as mock_lock:
        cm = AsyncMock()
        cm.__aenter__.return_value = False  # Not acquired
        cm.__aexit__.return_value = None
        mock_lock.return_value = cm

        service = PrecisionRepairService(mock_session, cal, redis=mock_redis)
        finding = AuditFinding(
            finding_id="f-lock",
            dataset="DAILY_PRICES",
            target_date=date(2026, 8, 7),
            audit_status=AuditStatus.PARTIAL,
            market="TWSE",
        )
        result = await service.execute_repair(finding)
        assert not result.executed
        assert "JOB_LOCK_BUSY" in (result.error or "")


# 13. Human print output executes cleanly
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
