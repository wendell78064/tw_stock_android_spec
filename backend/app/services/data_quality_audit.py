from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.domain.audit import (
    AuditStatus,
    DailyDataAuditReport,
    DailyPriceMarketAudit,
    DerivativesDatasetAudit,
    DuplicateAudit,
    HistoricalGapAudit,
    HistoricalGapSession,
    IndustryStrengthAudit,
    MarketSpotAudit,
    SecurityMasterAudit,
    TechnicalsAudit,
)
from app.domain.calendar import TradingCalendar
from app.repositories.models import (
    DailyPriceModel,
    FuturesContractModel,
    FuturesDailyPriceModel,
    FuturesProductModel,
    InstitutionFuturesPositionModel,
    MarketBreadthModel,
    MarketInstitutionalSpotModel,
    MarketMarginTradingModel,
    MarketModel,
    MarketSecuritiesLendingModel,
    OptionPutCallRatioModel,
    OptionStrikeOpenInterestModel,
    SecurityModel,
    TaxonomyStrengthSnapshotModel,
    TechnicalSnapshotModel,
    TraderConcentrationModel,
    VolatilityIndexModel,
)


class DataQualityAuditService:
    def __init__(self, session: AsyncSession, calendar: TradingCalendar | None = None):
        self.session = session
        self.calendar = calendar or WeekendOnlyCalendar()

    async def audit_date(self, target_date: date) -> DailyDataAuditReport:
        is_weekend = target_date.weekday() >= 5
        is_trading = self.calendar.is_trading_day(target_date)

        # 1. Audit Security Master
        sec_audit = await self._audit_security_master()

        # 2. Audit Daily Prices for TWSE and TPEX
        twse_daily = await self._audit_daily_prices(
            "TWSE", target_date, sec_audit.twse_common_stocks
        )
        tpex_daily = await self._audit_daily_prices(
            "TPEX", target_date, sec_audit.tpex_common_stocks
        )

        # Determine day_type:
        # If both markets have 0 daily prices and it is a weekday, mark HOLIDAY
        if is_weekend:
            day_type = "WEEKEND"
        elif twse_daily.rows_with_price == 0 and tpex_daily.rows_with_price == 0:
            day_type = "HOLIDAY"
        else:
            day_type = "TRADING_DAY"

        # 3. Audit Market Spot
        spot_audit = await self._audit_market_spot(target_date)

        # 4. Audit Derivatives (TAIFEX)
        deriv_audit = await self._audit_derivatives(target_date)

        # 5. Audit Technicals
        tech_audit = await self._audit_technicals(target_date, sec_audit.active_common_stocks)

        # 6. Audit Industry Strength
        ind_audit = await self._audit_industry_strength(target_date)

        # 7. Audit Duplicates
        dup_audit = await self._audit_duplicates(target_date)

        # 8. Compute Overall Status
        overall = self._compute_overall_status(
            day_type,
            twse_daily,
            tpex_daily,
            spot_audit,
            deriv_audit,
            tech_audit,
            ind_audit,
            dup_audit,
        )

        return DailyDataAuditReport(
            target_date=target_date,
            is_trading_day=is_trading and (day_type == "TRADING_DAY"),
            day_type=day_type,
            security_master=sec_audit,
            twse_daily=twse_daily,
            tpex_daily=tpex_daily,
            market_spot=spot_audit,
            derivatives=deriv_audit,
            technicals=tech_audit,
            industry_strength=ind_audit,
            duplicates=dup_audit,
            overall_status=overall,
        )

    async def _audit_security_master(self) -> SecurityMasterAudit:
        total_stmt = select(func.count()).select_from(SecurityModel)
        total = (await self.session.execute(total_stmt)).scalar() or 0

        twse_stmt = (
            select(func.count())
            .select_from(SecurityModel)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == "COMMON_STOCK",
                MarketModel.code == "TWSE",
            )
        )
        twse_stocks = (await self.session.execute(twse_stmt)).scalar() or 0

        tpex_stmt = (
            select(func.count())
            .select_from(SecurityModel)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == "COMMON_STOCK",
                MarketModel.code == "TPEX",
            )
        )
        tpex_stocks = (await self.session.execute(tpex_stmt)).scalar() or 0

        active_stocks = twse_stocks + tpex_stocks

        inactive_stmt = (
            select(func.count())
            .select_from(SecurityModel)
            .where(SecurityModel.is_active.is_(False))
        )
        inactive = (await self.session.execute(inactive_stmt)).scalar() or 0

        dup_stmt = select(func.count()).select_from(
            select(SecurityModel.market_id, SecurityModel.code)
            .group_by(SecurityModel.market_id, SecurityModel.code)
            .having(func.count() > 1)
            .subquery()
        )
        duplicates = (await self.session.execute(dup_stmt)).scalar() or 0

        status = AuditStatus.COMPLETE if (total > 0 and duplicates == 0) else AuditStatus.FAILED

        return SecurityMasterAudit(
            total_securities=total,
            active_common_stocks=active_stocks,
            twse_common_stocks=twse_stocks,
            tpex_common_stocks=tpex_stocks,
            inactive_securities=inactive,
            duplicate_count=duplicates,
            status=status,
        )

    async def _audit_daily_prices(
        self,
        market: str,
        target_date: date,
        expected_stocks: int,
    ) -> DailyPriceMarketAudit:
        # Join daily_prices with securities and markets
        stmt = (
            select(
                func.count(DailyPriceModel.id),
                func.count(DailyPriceModel.close),
                func.max(DailyPriceModel.trade_date),
            )
            .join(SecurityModel, DailyPriceModel.security_id == SecurityModel.id)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                MarketModel.code == market,
                SecurityModel.security_type == "COMMON_STOCK",
                SecurityModel.is_active.is_(True),
                DailyPriceModel.trade_date == target_date,
            )
        )
        res = (await self.session.execute(stmt)).first()
        total_rows = res[0] if res else 0
        valid_close_rows = res[1] if res else 0

        # Latest date in DB for this market
        latest_stmt = (
            select(func.max(DailyPriceModel.trade_date))
            .join(SecurityModel, DailyPriceModel.security_id == SecurityModel.id)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                MarketModel.code == market,
                SecurityModel.security_type == "COMMON_STOCK",
            )
        )
        latest_date = (await self.session.execute(latest_stmt)).scalar()

        # Check duplicates on (security_id, trade_date)
        dup_stmt = select(func.count()).select_from(
            select(DailyPriceModel.security_id, DailyPriceModel.trade_date)
            .join(SecurityModel, DailyPriceModel.security_id == SecurityModel.id)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                MarketModel.code == market,
                DailyPriceModel.trade_date == target_date,
            )
            .group_by(DailyPriceModel.security_id, DailyPriceModel.trade_date)
            .having(func.count() > 1)
            .subquery()
        )
        duplicates = (await self.session.execute(dup_stmt)).scalar() or 0

        trading_rows = valid_close_rows
        no_trade_rows = total_rows - valid_close_rows
        missing_count = max(0, expected_stocks - total_rows)
        coverage_ratio = (total_rows / expected_stocks) if expected_stocks > 0 else 1.0

        if total_rows == 0:
            status = AuditStatus.NO_DATA
        elif coverage_ratio >= 0.98 and duplicates == 0:
            status = AuditStatus.COMPLETE
        elif duplicates > 0:
            status = AuditStatus.FAILED
        else:
            status = AuditStatus.PARTIAL

        return DailyPriceMarketAudit(
            market=market,
            active_common_stocks=expected_stocks,
            expected_eligible=expected_stocks,
            rows_with_price=total_rows,
            trading_rows=trading_rows,
            suspended_or_no_trade_rows=no_trade_rows,
            missing_count=missing_count,
            coverage_ratio=round(coverage_ratio, 4),
            duplicate_count=duplicates,
            latest_date=latest_date,
            status=status,
        )

    async def _audit_market_spot(self, target_date: date) -> MarketSpotAudit:
        breadth_stmt = (
            select(func.count())
            .select_from(MarketBreadthModel)
            .where(MarketBreadthModel.trade_date == target_date)
        )
        breadth_rows = (await self.session.execute(breadth_stmt)).scalar() or 0

        margin_stmt = (
            select(func.count())
            .select_from(MarketMarginTradingModel)
            .where(MarketMarginTradingModel.trade_date == target_date)
        )
        margin_rows = (await self.session.execute(margin_stmt)).scalar() or 0

        lending_stmt = (
            select(func.count())
            .select_from(MarketSecuritiesLendingModel)
            .where(MarketSecuritiesLendingModel.trade_date == target_date)
        )
        lending_rows = (await self.session.execute(lending_stmt)).scalar() or 0

        inst_stmt = (
            select(func.count())
            .select_from(MarketInstitutionalSpotModel)
            .where(MarketInstitutionalSpotModel.trade_date == target_date)
        )
        inst_rows = (await self.session.execute(inst_stmt)).scalar() or 0

        dup_stmt = select(func.count()).select_from(
            select(MarketBreadthModel.market_code, MarketBreadthModel.trade_date)
            .where(MarketBreadthModel.trade_date == target_date)
            .group_by(MarketBreadthModel.market_code, MarketBreadthModel.trade_date)
            .having(func.count() > 1)
            .subquery()
        )
        duplicates = (await self.session.execute(dup_stmt)).scalar() or 0

        total_spot_rows = breadth_rows + margin_rows + lending_rows + inst_rows
        if total_spot_rows == 0:
            status = AuditStatus.NO_DATA
        elif breadth_rows >= 2 and margin_rows >= 2 and duplicates == 0:
            status = AuditStatus.COMPLETE
        elif duplicates > 0:
            status = AuditStatus.FAILED
        else:
            status = AuditStatus.PARTIAL

        return MarketSpotAudit(
            market_breadth_rows=breadth_rows,
            margin_trading_rows=margin_rows,
            securities_lending_rows=lending_rows,
            institutional_spot_rows=inst_rows,
            duplicate_count=duplicates,
            status=status,
        )

    async def _audit_derivatives(self, target_date: date) -> list[DerivativesDatasetAudit]:
        datasets: list[DerivativesDatasetAudit] = []

        # 1. FUTURES_PRODUCTS
        prod_cnt = (
            await self.session.execute(select(func.count()).select_from(FuturesProductModel))
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="FUTURES_PRODUCTS",
                row_count=prod_cnt,
                status=AuditStatus.COMPLETE if prod_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 2. FUTURES_CONTRACTS
        cntr_cnt = (
            await self.session.execute(select(func.count()).select_from(FuturesContractModel))
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="FUTURES_CONTRACTS",
                row_count=cntr_cnt,
                status=AuditStatus.COMPLETE if cntr_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 3. FUTURES_DAILY
        daily_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(FuturesDailyPriceModel)
                .where(FuturesDailyPriceModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="FUTURES_DAILY",
                row_count=daily_cnt,
                status=AuditStatus.COMPLETE if daily_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 4. FUTURES_INSTITUTIONAL
        inst_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(InstitutionFuturesPositionModel)
                .where(InstitutionFuturesPositionModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="FUTURES_INSTITUTIONAL",
                row_count=inst_cnt,
                status=AuditStatus.COMPLETE if inst_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 5. TRADER_CONCENTRATION
        conc_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(TraderConcentrationModel)
                .where(TraderConcentrationModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="TRADER_CONCENTRATION",
                row_count=conc_cnt,
                status=AuditStatus.COMPLETE if conc_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 6. OPTION_PUT_CALL
        pc_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(OptionPutCallRatioModel)
                .where(OptionPutCallRatioModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="OPTION_PUT_CALL",
                row_count=pc_cnt,
                status=AuditStatus.COMPLETE if pc_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 7. OPTION_STRIKE_OI
        oi_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(OptionStrikeOpenInterestModel)
                .where(OptionStrikeOpenInterestModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="OPTION_STRIKE_OI",
                row_count=oi_cnt,
                status=AuditStatus.COMPLETE if oi_cnt > 0 else AuditStatus.NO_DATA,
            )
        )

        # 8. VOLATILITY_INDEX (Maintains UNAVAILABLE status)
        vix_cnt = (
            await self.session.execute(
                select(func.count())
                .select_from(VolatilityIndexModel)
                .where(VolatilityIndexModel.trade_date == target_date)
            )
        ).scalar() or 0
        datasets.append(
            DerivativesDatasetAudit(
                dataset="VOLATILITY_INDEX",
                row_count=vix_cnt,
                status=AuditStatus.UNAVAILABLE,
                note="TAIFEX VIX feed unavailable via public OpenAPI/RWD",
            )
        )

        return datasets

    async def _audit_technicals(
        self,
        target_date: date,
        active_stocks: int,
    ) -> TechnicalsAudit:
        # Snapshots for target_date
        snap_stmt = (
            select(
                func.count(TechnicalSnapshotModel.id),
                func.count(TechnicalSnapshotModel.ma240),
            )
            .join(SecurityModel, TechnicalSnapshotModel.security_id == SecurityModel.id)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == "COMMON_STOCK",
                TechnicalSnapshotModel.trade_date == target_date,
                TechnicalSnapshotModel.price_basis == "RAW",
            )
        )
        res = (await self.session.execute(snap_stmt)).first()
        snapshots_count = res[0] if res else 0
        ma240_with_val = res[1] if res else 0

        # Latest snapshot date in DB
        max_date_stmt = select(func.max(TechnicalSnapshotModel.trade_date))
        latest_snap_date = (await self.session.execute(max_date_stmt)).scalar()

        # Duplicate check on (security_id, price_basis, trade_date)
        dup_stmt = select(func.count()).select_from(
            select(
                TechnicalSnapshotModel.security_id,
                TechnicalSnapshotModel.price_basis,
                TechnicalSnapshotModel.trade_date,
            )
            .where(TechnicalSnapshotModel.trade_date == target_date)
            .group_by(
                TechnicalSnapshotModel.security_id,
                TechnicalSnapshotModel.price_basis,
                TechnicalSnapshotModel.trade_date,
            )
            .having(func.count() > 1)
            .subquery()
        )
        duplicates = (await self.session.execute(dup_stmt)).scalar() or 0

        # MA240 integrity: check active stocks that have >= 240 historical prices up to target_date
        history_counts_subq = (
            select(
                DailyPriceModel.security_id,
                func.count(DailyPriceModel.id).label("price_count"),
            )
            .where(DailyPriceModel.trade_date <= target_date)
            .group_by(DailyPriceModel.security_id)
            .subquery()
        )

        eligible_stmt = (
            select(func.count())
            .select_from(SecurityModel)
            .join(history_counts_subq, SecurityModel.id == history_counts_subq.c.security_id)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == "COMMON_STOCK",
                history_counts_subq.c.price_count >= 240,
            )
        )
        ma240_eligible = (await self.session.execute(eligible_stmt)).scalar() or 0

        # If snapshots exist on target_date:
        if snapshots_count > 0:
            ma240_missing = max(0, min(snapshots_count, ma240_eligible) - ma240_with_val)
            stale_count = 0
            status = AuditStatus.COMPLETE if duplicates == 0 else AuditStatus.FAILED
        else:
            ma240_missing = 0
            stale_count = (
                active_stocks
                if (latest_snap_date and latest_snap_date < target_date)
                else 0
            )
            status = (
                AuditStatus.NO_DATA
                if (target_date.weekday() >= 5 or snapshots_count == 0)
                else AuditStatus.STALE
            )

        return TechnicalsAudit(
            active_stocks=active_stocks,
            snapshot_date=latest_snap_date if snapshots_count == 0 else target_date,
            snapshots_count=snapshots_count,
            stale_count=stale_count,
            ma240_eligible_count=ma240_eligible,
            ma240_valid_count=ma240_with_val,
            ma240_missing_count=ma240_missing,
            duplicate_count=duplicates,
            status=status,
        )

    async def _audit_industry_strength(self, target_date: date) -> IndustryStrengthAudit:
        stmt = (
            select(func.count())
            .select_from(TaxonomyStrengthSnapshotModel)
            .where(TaxonomyStrengthSnapshotModel.trade_date == target_date)
        )
        cnt = (await self.session.execute(stmt)).scalar() or 0

        latest_stmt = select(func.max(TaxonomyStrengthSnapshotModel.trade_date))
        latest_date = (await self.session.execute(latest_stmt)).scalar()

        if cnt > 0:
            status = AuditStatus.COMPLETE
            snap_date = target_date
        else:
            status = AuditStatus.NO_DATA
            snap_date = latest_date

        return IndustryStrengthAudit(
            snapshot_date=snap_date,
            snapshot_count=cnt,
            status=status,
        )

    async def _audit_duplicates(self, target_date: date) -> DuplicateAudit:
        # Securities duplicates on (market_id, code)
        sec_dup = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(SecurityModel.market_id, SecurityModel.code)
                    .group_by(SecurityModel.market_id, SecurityModel.code)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar() or 0

        # Daily price duplicates on target_date
        price_dup = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(DailyPriceModel.security_id, DailyPriceModel.trade_date)
                    .where(DailyPriceModel.trade_date == target_date)
                    .group_by(DailyPriceModel.security_id, DailyPriceModel.trade_date)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar() or 0

        # Technical snapshots duplicates on target_date
        tech_dup = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(
                        TechnicalSnapshotModel.security_id,
                        TechnicalSnapshotModel.price_basis,
                        TechnicalSnapshotModel.trade_date,
                    )
                    .where(TechnicalSnapshotModel.trade_date == target_date)
                    .group_by(
                        TechnicalSnapshotModel.security_id,
                        TechnicalSnapshotModel.price_basis,
                        TechnicalSnapshotModel.trade_date,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar() or 0

        # Market breadth duplicates on target_date
        spot_dup = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(MarketBreadthModel.market_code, MarketBreadthModel.trade_date)
                    .where(MarketBreadthModel.trade_date == target_date)
                    .group_by(MarketBreadthModel.market_code, MarketBreadthModel.trade_date)
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar() or 0

        # Futures daily duplicates on target_date
        deriv_dup = (
            await self.session.execute(
                select(func.count()).select_from(
                    select(
                        FuturesDailyPriceModel.contract_id,
                        FuturesDailyPriceModel.trade_date,
                        FuturesDailyPriceModel.session_type,
                    )
                    .where(FuturesDailyPriceModel.trade_date == target_date)
                    .group_by(
                        FuturesDailyPriceModel.contract_id,
                        FuturesDailyPriceModel.trade_date,
                        FuturesDailyPriceModel.session_type,
                    )
                    .having(func.count() > 1)
                    .subquery()
                )
            )
        ).scalar() or 0

        total_dup = sec_dup + price_dup + tech_dup + spot_dup + deriv_dup
        status = AuditStatus.COMPLETE if total_dup == 0 else AuditStatus.FAILED

        return DuplicateAudit(
            duplicate_securities=sec_dup,
            duplicate_daily_prices=price_dup,
            duplicate_technical_snapshots=tech_dup,
            duplicate_market_spot=spot_dup,
            duplicate_derivatives=deriv_dup,
            status=status,
        )

    def _compute_overall_status(
        self,
        day_type: str,
        twse_daily: DailyPriceMarketAudit,
        tpex_daily: DailyPriceMarketAudit,
        spot: MarketSpotAudit,
        derivatives: list[DerivativesDatasetAudit],
        technicals: TechnicalsAudit,
        industry_strength: IndustryStrengthAudit,
        duplicates: DuplicateAudit,
    ) -> AuditStatus:
        if duplicates.status == AuditStatus.FAILED:
            return AuditStatus.FAILED

        if day_type in ("WEEKEND", "HOLIDAY"):
            return AuditStatus.COMPLETE

        statuses = [
            twse_daily.status,
            tpex_daily.status,
            spot.status,
            technicals.status,
            industry_strength.status,
        ]
        # Include active derivatives (excluding VOLATILITY_INDEX which is UNAVAILABLE)
        for d in derivatives:
            if d.dataset != "VOLATILITY_INDEX":
                statuses.append(d.status)

        if any(s == AuditStatus.FAILED for s in statuses):
            return AuditStatus.FAILED
        if all(s == AuditStatus.COMPLETE for s in statuses):
            return AuditStatus.COMPLETE
        if all(s == AuditStatus.NO_DATA for s in statuses):
            return AuditStatus.NO_DATA
        return AuditStatus.PARTIAL

    async def audit_historical_gap(
        self,
        start_date: date,
        end_date: date,
        market: str | None = None,
    ) -> HistoricalGapAudit:
        # Get active common stocks expected per market
        sec_audit = await self._audit_security_master()
        expected_stocks = (
            sec_audit.twse_common_stocks
            if market == "TWSE"
            else (
                sec_audit.tpex_common_stocks
                if market == "TPEX"
                else sec_audit.active_common_stocks
            )
        )

        # Query all session counts in range grouped by trade_date
        query = (
            select(
                DailyPriceModel.trade_date,
                func.count(DailyPriceModel.id).label("actual_count"),
            )
            .join(SecurityModel, DailyPriceModel.security_id == SecurityModel.id)
            .join(MarketModel, SecurityModel.market_id == MarketModel.id)
            .where(
                DailyPriceModel.trade_date >= start_date,
                DailyPriceModel.trade_date <= end_date,
                SecurityModel.security_type == "COMMON_STOCK",
            )
        )
        if market:
            query = query.where(MarketModel.code == market)
        query = query.group_by(DailyPriceModel.trade_date)

        rows = (await self.session.execute(query)).all()
        session_counts = {r[0]: r[1] for r in rows}

        total_weekdays = 0
        trading_sessions = 0
        holiday_sessions = 0
        anomalous_sessions = 0
        anomalies: list[HistoricalGapSession] = []

        curr = start_date
        while curr <= end_date:
            if curr.weekday() < 5:
                total_weekdays += 1
                actual = session_counts.get(curr, 0)
                if actual == 0:
                    holiday_sessions += 1
                else:
                    trading_sessions += 1
                    ratio = (actual / expected_stocks) if expected_stocks > 0 else 1.0
                    # An anomaly is a trading session with abnormally low coverage (< 85%)
                    if ratio < 0.85:
                        anomalous_sessions += 1
                        anomalies.append(
                            HistoricalGapSession(
                                trade_date=curr,
                                market=market or "ALL",
                                expected=expected_stocks,
                                actual=actual,
                                coverage_ratio=round(ratio, 4),
                                status=AuditStatus.PARTIAL,
                                is_anomalous=True,
                                reason=f"Low coverage: {actual}/{expected_stocks} ({ratio:.1%})",
                            )
                        )
            curr += timedelta(days=1)

        status = AuditStatus.COMPLETE if anomalous_sessions == 0 else AuditStatus.PARTIAL

        return HistoricalGapAudit(
            market=market or "ALL",
            start_date=start_date,
            end_date=end_date,
            total_weekdays=total_weekdays,
            trading_sessions=trading_sessions,
            holiday_sessions=holiday_sessions,
            anomalous_sessions=anomalous_sessions,
            anomalies=anomalies,
            status=status,
        )
