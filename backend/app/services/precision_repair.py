from datetime import UTC, date, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.fake_derivatives import FakeDerivativesDataProvider
from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.official_spot import OfficialTpexProvider, OfficialTwseProvider
from app.adapters.taifex import OfficialTaifexProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.core.job_lock import distributed_job_lock
from app.domain.audit import (
    AuditFinding,
    AuditStatus,
    PrecisionRepairResult,
    RepairDecision,
    RepairDecisionOutcome,
    RepairScope,
    RepairScopeType,
)
from app.domain.calendar import TradingCalendar
from app.domain.pricing import PriceBasis, SecurityKey
from app.domain.security import MarketCode
from app.repositories.models import DailyPriceModel, IngestionRunModel, MarketModel, SecurityModel
from app.repositories.sql_derivatives import SqlDerivativesRepository
from app.repositories.sql_market_spot import SqlMarketSpotRepository
from app.repositories.sql_price import SqlPriceRepository
from app.services.daily_price_ingestion import (
    DailyPriceIngestionService,
    TechnicalCalculationService,
)
from app.services.data_quality_audit import DataQualityAuditService
from app.services.derivatives_ingestion import DERIVATIVE_DATASETS, DerivativesIngestionService
from app.services.industry_strength_calculation import IndustryStrengthCalculationService
from app.services.market_spot_ingestion import DATASETS as MARKET_SPOT_DATASETS
from app.services.market_spot_ingestion import MarketSpotIngestionService


class PrecisionRepairPlanner:
    def __init__(self, calendar: TradingCalendar | None = None):
        self.calendar = calendar or WeekendOnlyCalendar()

    def plan_repair(self, finding: AuditFinding) -> RepairDecision:
        # 1. Check TradingCalendar first: holidays and weekends are NOT repairable
        if not self.calendar.is_trading_day(finding.target_date):
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.HOLIDAY,
                reason=(
                    f"Date {finding.target_date.isoformat()} is a non-trading day "
                    "(weekend or holiday) per TradingCalendar"
                ),
            )

        # 2. Check known external provider capability limitations
        dataset_upper = finding.dataset.upper()
        if dataset_upper in ("VOLATILITY_INDEX", "TAIFEX_VIX", "VIX"):
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.UNAVAILABLE,
                reason=(
                    "Official historical Taiwan VIX is unavailable via public OpenAPI/RWD; "
                    "external capability limitation"
                ),
            )

        # 3. Check dataset support
        daily_price_datasets = {"DAILY_PRICES", "TWSE_DAILY", "TPEX_DAILY", "PRICES"}
        is_daily_price = dataset_upper in daily_price_datasets
        is_spot = dataset_upper in MARKET_SPOT_DATASETS or dataset_upper in ("MARKET_SPOT", "SPOT")
        is_derivatives = (
            dataset_upper in DERIVATIVE_DATASETS
            or dataset_upper in ("DERIVATIVES", "TAIFEX", "TAIFEX_PUT_CALL", "OPTION_PUT_CALL")
            or dataset_upper.startswith("TAIFEX_")
        )
        is_technicals = dataset_upper in ("TECHNICALS", "TECHNICAL_SNAPSHOTS")
        is_industry = dataset_upper in ("INDUSTRY_STRENGTH", "INDUSTRY_SNAPSHOTS")

        if not (is_daily_price or is_spot or is_derivatives or is_technicals or is_industry):
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.UNSUPPORTED,
                reason=f"Dataset {finding.dataset} does not support automatic precision repair",
            )

        # 4. Check status preconditions
        if finding.audit_status == AuditStatus.COMPLETE:
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.SKIP,
                reason="Audit status is already COMPLETE; no repair required",
            )

        # If data is not yet published (e.g. future date, or finding indicates not yet published)
        today = date.today()
        reason_lower = (finding.reason or "").lower()
        is_not_published_signal = (
            "not published" in reason_lower
            or "not yet published" in reason_lower
            or "publication pending" in reason_lower
            or "upstream publication" in reason_lower
        )
        if finding.target_date > today:
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.NOT_PUBLISHED,
                reason=(
                    f"Date {finding.target_date.isoformat()} is in the future; "
                    "data not published"
                ),
            )
        if finding.target_date == today and is_not_published_signal:
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.NOT_PUBLISHED,
                reason=(
                    f"Dataset {finding.dataset} for today {today.isoformat()} "
                    f"is not yet published upstream ({finding.reason})"
                ),
            )

        # 5. Build exact bounded repair scope
        try:
            if finding.security_code and finding.market:
                scope = RepairScope(
                    scope_type=RepairScopeType.SECURITY_DATE,
                    dataset=finding.dataset,
                    target_date=finding.target_date,
                    market=finding.market,
                    security_code=finding.security_code,
                )
            elif (
                finding.start_date
                and finding.end_date
                and (finding.start_date != finding.end_date)
            ):
                scope = RepairScope(
                    scope_type=RepairScopeType.DATE_RANGE,
                    dataset=finding.dataset,
                    start_date=finding.start_date,
                    end_date=finding.end_date,
                    market=finding.market,
                )
            else:
                scope = RepairScope(
                    scope_type=RepairScopeType.DATASET_DATE,
                    dataset=finding.dataset,
                    target_date=finding.target_date,
                    market=finding.market,
                )
        except ValueError as err:
            return RepairDecision(
                finding_id=finding.finding_id,
                outcome=RepairDecisionOutcome.UNSUPPORTED,
                reason=f"Invalid or unbounded repair scope: {err}",
            )

        return RepairDecision(
            finding_id=finding.finding_id,
            outcome=RepairDecisionOutcome.REPAIRABLE,
            reason=f"Bounded precision repair planned for scope {scope.scope_type.value}",
            scope=scope,
        )


class PrecisionRepairService:
    def __init__(
        self,
        session: AsyncSession,
        calendar: TradingCalendar | None = None,
        provider_mode: str = "official",
        redis: Redis | None = None,
    ):
        self.session = session
        self.calendar = calendar or WeekendOnlyCalendar()
        self.provider_mode = provider_mode
        self.redis = redis
        self.planner = PrecisionRepairPlanner(self.calendar)
        self.audit_service = DataQualityAuditService(self.session, self.calendar)

    async def execute_repair(
        self, finding: AuditFinding, skip_lock: bool = False
    ) -> PrecisionRepairResult:
        decision = self.planner.plan_repair(finding)

        if decision.outcome != RepairDecisionOutcome.REPAIRABLE or not decision.scope:
            return PrecisionRepairResult(
                finding_id=finding.finding_id,
                decision=decision,
                executed=False,
                status_before=finding.audit_status,
                status_after=finding.audit_status,
                error=None,
                executed_at=datetime.now(UTC),
            )

        scope = decision.scope

        # Concurrency safety: Mutually exclude conflicting market-data mutations with Daily Pipeline
        if self.redis is not None and not skip_lock:
            async with distributed_job_lock(
                self.redis, "daily-pipeline", ttl_seconds=600
            ) as acquired:
                if not acquired:
                    return PrecisionRepairResult(
                        finding_id=finding.finding_id,
                        decision=decision,
                        executed=False,
                        status_before=finding.audit_status,
                        status_after=finding.audit_status,
                        error="JOB_LOCK_BUSY: Pipeline/Repair lock held by another runner",
                        executed_at=datetime.now(UTC),
                    )
                return await self._do_repair_and_reaudit(finding, decision, scope)
        else:
            return await self._do_repair_and_reaudit(finding, decision, scope)

    async def _do_repair_and_reaudit(
        self,
        finding: AuditFinding,
        decision: RepairDecision,
        scope: RepairScope,
    ) -> PrecisionRepairResult:
        now = datetime.now(UTC)
        inserted = 0
        updated = 0
        run_id_str: str | None = None
        err_msg: str | None = None

        try:
            inserted, updated, run_id_str = await self._dispatch_repair(scope)
        except Exception as ex:
            err_msg = str(ex)

        # Re-audit the exact scope with real data-quality checks
        re_audit_status, re_audit_report = await self._re_audit_scope(scope)

        # Audit trail persistence: record repair execution metadata in ingestion_runs
        persisted_run_id = await self._persist_repair_audit_trail(
            finding=finding,
            decision=decision,
            scope=scope,
            status_before=finding.audit_status,
            status_after=re_audit_status,
            inserted=inserted,
            updated=updated,
            error=err_msg,
            run_id_str=run_id_str,
            executed_at=now,
        )

        return PrecisionRepairResult(
            finding_id=finding.finding_id,
            decision=decision,
            executed=(err_msg is None),
            status_before=finding.audit_status,
            status_after=re_audit_status,
            repaired_records_inserted=inserted,
            repaired_records_updated=updated,
            error=err_msg,
            ingestion_run_id=persisted_run_id or run_id_str,
            re_audit_report=re_audit_report,
            executed_at=now,
        )

    async def _persist_repair_audit_trail(
        self,
        finding: AuditFinding,
        decision: RepairDecision,
        scope: RepairScope,
        status_before: AuditStatus,
        status_after: AuditStatus,
        inserted: int,
        updated: int,
        error: str | None,
        run_id_str: str | None,
        executed_at: datetime,
    ) -> str | None:
        try:
            import json
            from uuid import UUID, uuid4

            try:
                run_uuid = UUID(run_id_str) if run_id_str else uuid4()
            except (ValueError, AttributeError):
                run_uuid = uuid4()
            # If run was already created in ingestion_runs, update its error_message or metadata
            existing = await self.session.get(IngestionRunModel, run_uuid)
            meta = {
                "repair_finding_id": finding.finding_id,
                "repair_decision": decision.outcome.value,
                "repair_scope": scope.scope_type.value,
                "status_before": status_before.value,
                "status_after": status_after.value,
                "scope_dataset": scope.dataset,
                "target_date": scope.target_date.isoformat() if scope.target_date else None,
            }
            if existing is not None:
                existing.error_message = (
                    f"{existing.error_message}; {json.dumps(meta)}"
                    if existing.error_message
                    else json.dumps(meta)
                )
                await self.session.commit()
                return str(existing.id)
            else:
                repair_run = IngestionRunModel(
                    id=run_uuid,
                    provider="PRECISION_REPAIR",
                    dataset=scope.dataset,
                    started_at=executed_at,
                    finished_at=datetime.now(UTC),
                    status=status_after.value if not error else "FAILED",
                    fetched_count=inserted + updated,
                    inserted_count=inserted,
                    updated_count=updated,
                    rejected_count=0 if not error else 1,
                    error_message=error or json.dumps(meta),
                )
                self.session.add(repair_run)
                await self.session.commit()
                return str(repair_run.id)
        except Exception:
            # Audit trail persistence should not abort repair result
            return run_id_str

    async def _dispatch_repair(self, scope: RepairScope) -> tuple[int, int, str | None]:
        dataset = scope.dataset.upper()
        inserted = 0
        updated = 0
        run_id: str | None = None

        if dataset in ("DAILY_PRICES", "TWSE_DAILY", "TPEX_DAILY", "PRICES"):
            inserted, updated, run_id = await self._repair_daily_prices(scope)
        elif dataset in MARKET_SPOT_DATASETS or dataset in ("MARKET_SPOT", "SPOT"):
            inserted, updated, run_id = await self._repair_market_spot(scope)
        elif dataset in DERIVATIVE_DATASETS or dataset in ("DERIVATIVES", "TAIFEX"):
            inserted, updated, run_id = await self._repair_derivatives(scope)
        elif dataset in ("TECHNICALS", "TECHNICAL_SNAPSHOTS"):
            inserted, updated, run_id = await self._repair_technicals(scope)
        elif dataset in ("INDUSTRY_STRENGTH", "INDUSTRY_SNAPSHOTS"):
            inserted, updated, run_id = await self._repair_industry_strength(scope)
        else:
            raise ValueError(f"Unsupported dataset for repair execution: {scope.dataset}")

        return inserted, updated, run_id

    async def _repair_daily_prices(self, scope: RepairScope) -> tuple[int, int, str | None]:
        repo = SqlPriceRepository(self.session)
        service = DailyPriceIngestionService(self.session, repo, self.calendar)

        target_date = scope.target_date
        security_key: SecurityKey | None = None
        if scope.security_code and scope.market:
            security_key = SecurityKey(MarketCode(scope.market), scope.security_code)

        # Select provider based on provider_mode and market
        providers = []
        if self.provider_mode == "fake":
            providers.append(FakeMarketDataProvider())
        else:
            if scope.market == "TWSE":
                providers.append(TwseSecurityProvider())
            elif scope.market == "TPEX":
                providers.append(TpexSecurityProvider())
            else:
                providers.extend([TwseSecurityProvider(), TpexSecurityProvider()])

        tot_ins = 0
        tot_upd = 0
        last_run_id = None

        if scope.scope_type == RepairScopeType.DATE_RANGE:
            cur = scope.start_date
            while cur and cur <= scope.end_date:
                if self.calendar.is_trading_day(cur):
                    for prov in providers:
                        run = await service.synchronize(
                            prov,
                            trade_date=cur,
                            security=security_key,
                        )
                        tot_ins += run.inserted_count
                        tot_upd += run.updated_count
                        last_run_id = str(run.id)
                cur = cur.fromordinal(cur.toordinal() + 1)
        else:
            for prov in providers:
                run = await service.synchronize(
                    prov,
                    trade_date=target_date,
                    security=security_key,
                )
                tot_ins += run.inserted_count
                tot_upd += run.updated_count
                last_run_id = str(run.id)

        # Recalculate technicals for affected security if exact security was repaired
        if security_key:
            tech_svc = TechnicalCalculationService(repo)
            await tech_svc.recalculate(security_key, PriceBasis.RAW)

        return tot_ins, tot_upd, last_run_id

    async def _repair_market_spot(self, scope: RepairScope) -> tuple[int, int, str | None]:
        target_date = scope.target_date or date.today()
        repo = SqlMarketSpotRepository(self.session)
        service = MarketSpotIngestionService(self.session, repo)

        if self.provider_mode == "fake":
            providers = [FakeMarketDataProvider()]
        else:
            if scope.market == "TWSE":
                providers = [OfficialTwseProvider()]
            elif scope.market == "TPEX":
                providers = [OfficialTpexProvider()]
            else:
                providers = [OfficialTwseProvider(), OfficialTpexProvider()]

        datasets_to_repair = (
            [scope.dataset]
            if scope.dataset in MARKET_SPOT_DATASETS
            else list(MARKET_SPOT_DATASETS.keys())
        )

        tot_ins = 0
        tot_upd = 0
        last_run_id = None
        for prov in providers:
            for ds in datasets_to_repair:
                run = await service.synchronize_dataset(prov, ds, target_date)
                tot_ins += run.inserted_count
                tot_upd += run.updated_count
                last_run_id = str(run.id)

        return tot_ins, tot_upd, last_run_id

    async def _repair_derivatives(self, scope: RepairScope) -> tuple[int, int, str | None]:
        target_date = scope.target_date or date.today()
        repo = SqlDerivativesRepository(self.session)
        service = DerivativesIngestionService(self.session, repo)

        provider = (
            FakeDerivativesDataProvider()
            if self.provider_mode == "fake"
            else OfficialTaifexProvider()
        )

        datasets_to_repair = (
            [scope.dataset]
            if scope.dataset in DERIVATIVE_DATASETS
            else [k for k in DERIVATIVE_DATASETS.keys() if k != "VOLATILITY_INDEX"]
        )

        tot_ins = 0
        tot_upd = 0
        last_run_id = None
        for ds in datasets_to_repair:
            if ds == "VOLATILITY_INDEX":
                continue  # VIX is external capability unavailable
            run = await service.synchronize_dataset(provider, ds, target_date)
            tot_ins += run.inserted_count
            tot_upd += run.updated_count
            last_run_id = str(run.id)

        return tot_ins, tot_upd, last_run_id

    async def _repair_technicals(self, scope: RepairScope) -> tuple[int, int, str | None]:
        del scope.target_date
        repo = SqlPriceRepository(self.session)
        tech_svc = TechnicalCalculationService(repo)

        if scope.security_code and scope.market:
            key = SecurityKey(MarketCode(scope.market), scope.security_code)
            count = await tech_svc.recalculate(key, PriceBasis.RAW)
            return count, 0, None

        # Re-calc for active stocks
        stmt = (
            select(MarketModel.code, SecurityModel.code)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == "COMMON_STOCK",
            )
        )
        if scope.market:
            stmt = stmt.where(MarketModel.code == scope.market)
        rows = (await self.session.execute(stmt)).all()
        total_calculated = 0
        for m, c in rows:
            cnt = await tech_svc.recalculate(SecurityKey(MarketCode(m), c), PriceBasis.RAW)
            total_calculated += cnt

        return total_calculated, 0, None

    async def _repair_industry_strength(self, scope: RepairScope) -> tuple[int, int, str | None]:
        target_date = scope.target_date or date.today()
        # IndustryStrengthCalculationService expects sync session, wrap via sync_session
        calc_svc = IndustryStrengthCalculationService(self.session.sync_session)
        res = calc_svc.calculate_for_date(target_date)
        return res["inserted"], res["updated"], None

    async def _re_audit_scope(self, scope: RepairScope) -> tuple[AuditStatus, dict[str, Any]]:
        target_date = scope.target_date or scope.end_date or date.today()
        dataset = scope.dataset.upper()

        if (
            scope.scope_type == RepairScopeType.SECURITY_DATE
            and scope.market
            and scope.security_code
        ):
            # Check if this exact security has a valid price row on target_date
            stmt = (
                select(DailyPriceModel)
                .join(SecurityModel, DailyPriceModel.security_id == SecurityModel.id)
                .join(MarketModel, SecurityModel.market_id == MarketModel.id)
                .where(
                    MarketModel.code == scope.market,
                    SecurityModel.code == scope.security_code,
                    DailyPriceModel.trade_date == target_date,
                )
            )
            row = (await self.session.execute(stmt)).scalars().first()
            if row is None:
                return AuditStatus.FAILED, {
                    "security": f"{scope.market}:{scope.security_code}",
                    "trade_date": target_date.isoformat(),
                    "status": "FAILED",
                    "reason": "Price record still missing after repair",
                }

            # Canonical Data Quality validation on row:
            # 1. Trading row must have valid OHLC consistency
            #    (high >= max(open, close), low <= min(open, close), high >= low)
            # 2. Non-negative volume
            has_trade = row.close is not None
            if has_trade:
                if any(v is None for v in (row.open, row.high, row.low, row.close)):
                    return AuditStatus.FAILED, {
                        "security": f"{scope.market}:{scope.security_code}",
                        "trade_date": target_date.isoformat(),
                        "status": "FAILED",
                        "reason": "INVALID_OHLC: Trading row has missing OHLC components",
                    }
                o, h, l_val, c = float(row.open), float(row.high), float(row.low), float(row.close)
                if h < max(o, c) or l_val > min(o, c) or h < l_val:
                    return AuditStatus.FAILED, {
                        "security": f"{scope.market}:{scope.security_code}",
                        "trade_date": target_date.isoformat(),
                        "status": "FAILED",
                        "reason": "INVALID_OHLC: High/Low bounds violated against Open/Close",
                    }
            if row.volume_shares is not None and row.volume_shares < 0:
                return AuditStatus.FAILED, {
                    "security": f"{scope.market}:{scope.security_code}",
                    "trade_date": target_date.isoformat(),
                    "status": "FAILED",
                    "reason": "NEGATIVE_VOLUME: Share volume cannot be negative",
                }

            return AuditStatus.COMPLETE, {
                "security": f"{scope.market}:{scope.security_code}",
                "trade_date": target_date.isoformat(),
                "has_trade": has_trade,
                "close": str(row.close) if has_trade else None,
                "status": "COMPLETE",
            }

        # For dataset_date or general date scope, run daily audit
        daily_report = await self.audit_service.audit_date(target_date)
        report_dict = daily_report.to_dict()

        if dataset in ("TWSE_DAILY", "TPEX_DAILY", "DAILY_PRICES", "PRICES"):
            market = scope.market or (
                "TWSE" if "TWSE" in dataset else ("TPEX" if "TPEX" in dataset else None)
            )
            if market == "TWSE":
                return daily_report.twse_daily.status, report_dict.get("twse_daily", {})
            elif market == "TPEX":
                return daily_report.tpex_daily.status, report_dict.get("tpex_daily", {})
            else:
                twse_stat = daily_report.twse_daily.status
                tpex_stat = daily_report.tpex_daily.status
                combined = (
                    AuditStatus.COMPLETE
                    if (twse_stat == AuditStatus.COMPLETE and tpex_stat == AuditStatus.COMPLETE)
                    else AuditStatus.PARTIAL
                )
                return combined, {
                    "twse": report_dict.get("twse_daily"),
                    "tpex": report_dict.get("tpex_daily"),
                }

        elif dataset in MARKET_SPOT_DATASETS or dataset in ("MARKET_SPOT", "SPOT"):
            return daily_report.market_spot.status, report_dict.get("market_spot", {})

        elif dataset in DERIVATIVE_DATASETS or dataset in ("DERIVATIVES", "TAIFEX"):
            # find matching dataset in report
            for d in daily_report.derivatives:
                if d.dataset == dataset:
                    return d.status, {
                        "dataset": d.dataset,
                        "status": str(d.status),
                        "rows": d.row_count,
                    }
            return AuditStatus.COMPLETE, {"status": "COMPLETE"}

        elif dataset in ("TECHNICALS", "TECHNICAL_SNAPSHOTS"):
            return daily_report.technicals.status, report_dict.get("technicals", {})

        elif dataset in ("INDUSTRY_STRENGTH", "INDUSTRY_SNAPSHOTS"):
            return daily_report.industry_strength.status, report_dict.get("industry_strength", {})

        return daily_report.overall_status, report_dict
