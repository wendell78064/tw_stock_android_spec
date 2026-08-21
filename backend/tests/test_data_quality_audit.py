from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.cli.audit_market_data import print_human_daily_report, print_human_gap_report
from app.domain.audit import (
    AuditStatus,
    DailyDataAuditReport,
    DailyPriceMarketAudit,
    DerivativesDatasetAudit,
    DuplicateAudit,
    HistoricalGapAudit,
    IndustryStrengthAudit,
    MarketSpotAudit,
    SecurityMasterAudit,
    TechnicalsAudit,
)
from app.services.data_quality_audit import DataQualityAuditService


class MockTradingCalendar:
    def __init__(self, non_trading_dates: set[date] | None = None):
        self.non_trading_dates = non_trading_dates or set()

    def is_trading_day(self, value: date) -> bool:
        if value in self.non_trading_dates:
            return False
        return value.weekday() < 5

    def previous_trading_day(self, value: date) -> date:
        return value


def _create_mock_session_for_audit(
    *,
    total_sec: int = 1900,
    twse_stocks: int = 1000,
    tpex_stocks: int = 800,
    inactive_sec: int = 50,
    dup_sec: int = 0,
    twse_prices: int = 1000,
    twse_closes: int = 995,
    twse_dup: int = 0,
    tpex_prices: int = 800,
    tpex_closes: int = 790,
    tpex_dup: int = 0,
    failed_runs: int = 0,
    breadth_rows: int = 2,
    margin_rows: int = 2,
    lending_rows: int = 1,
    inst_rows: int = 2,
    spot_dup: int = 0,
    futures_prod: int = 2,
    futures_cntr: int = 10,
    futures_daily: int = 10,
    futures_inst: int = 6,
    trader_conc: int = 10,
    option_pc: int = 1,
    option_oi: int = 20,
    vix_cnt: int = 0,
    deriv_dup: int = 0,
    tech_snaps: int = 1800,
    tech_ma240_val: int = 1600,
    tech_ma240_elig: int = 1600,
    tech_dup: int = 0,
    latest_tech_date: date | None = date(2026, 8, 20),
    ind_snaps: int = 30,
) -> AsyncMock:
    session = AsyncMock()

    async def execute_side_effect(stmt):
        mock_result = MagicMock()
        try:
            compiled = stmt.compile()
            params = compiled.params
        except Exception:
            params = {}
        query_str = str(stmt).lower()

        # Duplicate check on securities
        if (
            "from (select securities.market_id" in query_str
            or "securities.market_id, securities.code" in query_str
        ):
            mock_result.scalar.return_value = dup_sec
            return mock_result

        # Total securities
        if "where securities.is_active = false" in query_str:
            mock_result.scalar.return_value = inactive_sec
            return mock_result
        if "from securities" in query_str and "join markets" in query_str:
            if "daily_prices" not in query_str:
                code_val = params.get("code_1") or params.get("code_2") or params.get("code")
                if code_val == "TWSE" or "twse" in str(params).lower():
                    mock_result.scalar.return_value = twse_stocks
                elif code_val == "TPEX" or "tpex" in str(params).lower():
                    mock_result.scalar.return_value = tpex_stocks
                else:
                    mock_result.scalar.return_value = twse_stocks
                return mock_result

        if "select count(*) as count_1 \nfrom securities" in query_str and "where" not in query_str:
            mock_result.scalar.return_value = total_sec
            return mock_result

        # Failed ingestion runs check
        if "from ingestion_runs" in query_str:
            mock_result.scalar.return_value = failed_runs
            return mock_result

        # Duplicate check on daily_prices
        if "from (select daily_prices.security_id" in query_str:
            code_val = params.get("code_1") or params.get("code_2") or params.get("code")
            if code_val == "TPEX" or "tpex" in str(params).lower():
                mock_result.scalar.return_value = tpex_dup
            else:
                mock_result.scalar.return_value = twse_dup
            return mock_result

        # Daily prices for TWSE or TPEX
        if "daily_prices" in query_str and "markets" in query_str:
            code_val = params.get("code_1") or params.get("code_2") or params.get("code")
            if code_val == "TPEX" or "tpex" in str(params).lower():
                mock_result.first.return_value = (tpex_prices, tpex_closes, date(2026, 8, 20))
                mock_result.scalar.return_value = date(2026, 8, 20)
            else:
                mock_result.first.return_value = (twse_prices, twse_closes, date(2026, 8, 20))
                mock_result.scalar.return_value = date(2026, 8, 20)
            return mock_result
        if "daily_prices" in query_str and "join securities" in query_str:
            mock_result.first.return_value = (twse_prices, twse_closes, date(2026, 8, 20))
            mock_result.scalar.return_value = date(2026, 8, 20)
            return mock_result

        # Market spot
        if "from (select market_breadth.market_code" in query_str:
            mock_result.scalar.return_value = spot_dup
            return mock_result
        if "market_breadth" in query_str:
            mock_result.scalar.return_value = breadth_rows
            return mock_result
        if "market_margin_trading" in query_str:
            mock_result.scalar.return_value = margin_rows
            return mock_result
        if "market_securities_lending" in query_str:
            mock_result.scalar.return_value = lending_rows
            return mock_result
        if "market_institutional_spot" in query_str:
            mock_result.scalar.return_value = inst_rows
            return mock_result

        # Derivatives
        if "from (select futures_daily_prices" in query_str:
            mock_result.scalar.return_value = deriv_dup
            return mock_result
        if "futures_products" in query_str:
            mock_result.scalar.return_value = futures_prod
            return mock_result
        if "futures_contracts" in query_str:
            mock_result.scalar.return_value = futures_cntr
            return mock_result
        if "futures_daily_prices" in query_str:
            mock_result.scalar.return_value = futures_daily
            return mock_result
        if "institution_futures_positions" in query_str:
            mock_result.scalar.return_value = futures_inst
            return mock_result
        if "trader_concentration" in query_str:
            mock_result.scalar.return_value = trader_conc
            return mock_result
        if "option_put_call_ratios" in query_str:
            mock_result.scalar.return_value = option_pc
            return mock_result
        if "option_strike_open_interest" in query_str:
            mock_result.scalar.return_value = option_oi
            return mock_result
        if "volatility_indexes" in query_str:
            mock_result.scalar.return_value = vix_cnt
            return mock_result

        # Technicals
        if "from (select technical_snapshots" in query_str:
            mock_result.scalar.return_value = tech_dup
            return mock_result
        if "technical_snapshots" in query_str and "join securities" in query_str:
            mock_result.first.return_value = (tech_snaps, tech_ma240_val)
            mock_result.scalar.return_value = latest_tech_date
            return mock_result
        if "select max(technical_snapshots.trade_date)" in query_str:
            mock_result.scalar.return_value = latest_tech_date
            return mock_result
        if "price_count >= :price_count_1" in query_str or "price_count" in query_str:
            mock_result.scalar.return_value = tech_ma240_elig
            return mock_result

        # Industry strength
        if "taxonomy_strength_snapshots" in query_str:
            mock_result.scalar.return_value = ind_snaps
            return mock_result

        # Fallback
        mock_result.scalar.return_value = 0
        mock_result.first.return_value = (0, 0, None)
        mock_result.all.return_value = []
        return mock_result

    session.execute = AsyncMock(side_effect=execute_side_effect)
    return session


@pytest.mark.asyncio
async def test_audit_normal_complete_trading_day() -> None:
    session = _create_mock_session_for_audit()
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.day_type == "TRADING_DAY"
    assert report.is_trading_day is True
    assert report.security_master.status is AuditStatus.COMPLETE
    assert report.security_master.duplicate_count == 0
    assert report.twse_daily.status is AuditStatus.COMPLETE
    assert report.tpex_daily.status is AuditStatus.COMPLETE
    assert report.market_spot.status is AuditStatus.COMPLETE
    assert report.technicals.status is AuditStatus.COMPLETE
    assert report.technicals.ma240_missing_count == 0
    assert report.duplicates.status is AuditStatus.COMPLETE
    assert report.overall_status is AuditStatus.COMPLETE


@pytest.mark.asyncio
async def test_audit_volatility_index_unavailable_is_expected() -> None:
    session = _create_mock_session_for_audit()
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    vix_audit = next(d for d in report.derivatives if d.dataset == "VOLATILITY_INDEX")
    assert vix_audit.status is AuditStatus.UNAVAILABLE
    assert vix_audit.note is not None
    # Unavailable VIX must NOT cause overall audit to fail
    assert report.overall_status is AuditStatus.COMPLETE


@pytest.mark.asyncio
async def test_audit_weekend_day() -> None:
    # 2026-08-22 is Saturday
    session = _create_mock_session_for_audit(
        twse_prices=0, twse_closes=0, tpex_prices=0, tpex_closes=0
    )
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 22))

    assert report.day_type == "WEEKEND"
    assert report.is_trading_day is False
    assert report.twse_daily.status is AuditStatus.NO_DATA
    assert report.tpex_daily.status is AuditStatus.NO_DATA
    # On weekend, 0 daily prices is normal, overall status is COMPLETE
    assert report.overall_status is AuditStatus.COMPLETE


@pytest.mark.asyncio
async def test_audit_holiday_when_calendar_says_not_trading_day() -> None:
    # Holiday on weekday (e.g. 2026-04-06 Monday Tomb Sweeping makeup holiday)
    cal = MockTradingCalendar(non_trading_dates={date(2026, 4, 6)})
    session = _create_mock_session_for_audit(
        twse_prices=0, twse_closes=0, tpex_prices=0, tpex_closes=0
    )
    service = DataQualityAuditService(session, calendar=cal)
    report = await service.audit_date(date(2026, 4, 6))

    assert report.day_type == "HOLIDAY"
    assert report.is_trading_day is False
    assert report.twse_daily.status is AuditStatus.NO_DATA
    assert report.overall_status is AuditStatus.COMPLETE


@pytest.mark.asyncio
async def test_audit_trading_day_upstream_not_published_is_no_data() -> None:
    # Trading day before 15:30 CST: rows == 0, failed_runs == 0
    # Must NOT be classified as HOLIDAY!
    session = _create_mock_session_for_audit(
        twse_prices=0, twse_closes=0, tpex_prices=0, tpex_closes=0, failed_runs=0
    )
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.day_type == "TRADING_DAY"
    assert report.is_trading_day is True
    assert report.twse_daily.status is AuditStatus.NO_DATA
    assert report.tpex_daily.status is AuditStatus.NO_DATA


@pytest.mark.asyncio
async def test_audit_trading_day_ingestion_failure_is_failed() -> None:
    # Trading day with ingestion failure in ingestion_runs: rows == 0, failed_runs > 0
    session = _create_mock_session_for_audit(
        twse_prices=0, twse_closes=0, failed_runs=1
    )
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.day_type == "TRADING_DAY"
    assert report.is_trading_day is True
    assert report.twse_daily.status is AuditStatus.FAILED
    assert report.overall_status is AuditStatus.FAILED


@pytest.mark.asyncio
async def test_audit_stale_technical_detected() -> None:
    # Technical snapshots missing for target_date and latest date is in the past
    session = _create_mock_session_for_audit(
        tech_snaps=0,
        latest_tech_date=date(2026, 8, 19),
    )
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.technicals.stale_count == 1800
    assert report.technicals.status is AuditStatus.STALE
    assert report.overall_status is AuditStatus.STALE


@pytest.mark.asyncio
async def test_audit_duplicate_detection_causes_failed_status() -> None:
    session = _create_mock_session_for_audit(twse_dup=2)
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.twse_daily.duplicate_count == 2
    assert report.twse_daily.status is AuditStatus.FAILED
    assert report.duplicates.status is AuditStatus.FAILED
    assert report.overall_status is AuditStatus.FAILED


@pytest.mark.asyncio
async def test_audit_partial_twse_coverage() -> None:
    # Coverage 700 / 1000 = 70% -> PARTIAL
    session = _create_mock_session_for_audit(twse_prices=700, twse_closes=690)
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.twse_daily.coverage_ratio == 0.7
    assert report.twse_daily.status is AuditStatus.PARTIAL
    assert report.overall_status is AuditStatus.PARTIAL


@pytest.mark.asyncio
async def test_audit_legitimate_no_trade_stocks_handled_properly() -> None:
    # 995 trading, 5 halted -> 1000 rows with price (100% coverage)
    session = _create_mock_session_for_audit(twse_prices=1000, twse_closes=995)
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    assert report.twse_daily.trading_rows == 995
    assert report.twse_daily.suspended_or_no_trade_rows == 5
    assert report.twse_daily.missing_count == 0
    assert report.twse_daily.status is AuditStatus.COMPLETE


@pytest.mark.asyncio
async def test_audit_json_serialization() -> None:
    session = _create_mock_session_for_audit()
    service = DataQualityAuditService(session)
    report = await service.audit_date(date(2026, 8, 20))

    data_dict = report.to_dict()
    assert isinstance(data_dict, dict)
    assert data_dict["target_date"] == "2026-08-20"
    assert data_dict["overall_status"] == "COMPLETE"
    assert data_dict["twse_daily"]["market"] == "TWSE"
    assert isinstance(data_dict["derivatives"], list)


@pytest.mark.asyncio
async def test_historical_gap_audit_detects_anomalies() -> None:
    session = AsyncMock()

    # Mock security counts
    sec_audit_mock = MagicMock()
    sec_audit_mock.scalar.return_value = 1000

    # Mock historical daily price counts:
    # 2024-08-05 (1000), 2024-08-06 (1000), 2024-08-07 (500 - anomaly), 2024-08-08 (0 - holiday)
    hist_rows_mock = MagicMock()
    hist_rows_mock.all.return_value = [
        (date(2024, 8, 5), 1000),
        (date(2024, 8, 6), 1000),
        (date(2024, 8, 7), 500),  # Low coverage
    ]

    async def execute_side_effect(stmt):
        q = str(stmt).lower()
        if "from securities" in q and "group by" not in q:
            return sec_audit_mock
        if "daily_prices" in q and "group by daily_prices.trade_date" in q:
            return hist_rows_mock
        m = MagicMock()
        m.scalar.return_value = 0
        return m

    session.execute = AsyncMock(side_effect=execute_side_effect)

    service = DataQualityAuditService(session)
    gap_report = await service.audit_historical_gap(
        start_date=date(2024, 8, 5),
        end_date=date(2024, 8, 8),
        market="TWSE",
    )

    assert gap_report.total_weekdays == 4
    assert gap_report.trading_sessions == 3
    assert gap_report.holiday_sessions == 1
    assert gap_report.anomalous_sessions == 1
    assert len(gap_report.anomalies) == 1
    assert gap_report.anomalies[0].trade_date == date(2024, 8, 7)
    assert gap_report.anomalies[0].coverage_ratio == 0.5
    assert gap_report.status is AuditStatus.PARTIAL


def test_print_human_reports_execute_without_error(capsys) -> None:
    sec = SecurityMasterAudit(1900, 1800, 1000, 800, 100, 0, AuditStatus.COMPLETE)
    twse = DailyPriceMarketAudit(
        "TWSE", 1000, 1000, 1000, 995, 5, 0, 1.0, 0, date(2026, 8, 20), AuditStatus.COMPLETE
    )
    tpex = DailyPriceMarketAudit(
        "TPEX", 800, 800, 800, 790, 10, 0, 1.0, 0, date(2026, 8, 20), AuditStatus.COMPLETE
    )
    spot = MarketSpotAudit(2, 2, 1, 2, 0, AuditStatus.COMPLETE)
    deriv = [DerivativesDatasetAudit("FUTURES_DAILY", 10, AuditStatus.COMPLETE)]
    tech = TechnicalsAudit(
        1800, date(2026, 8, 20), 1800, 0, 1600, 1600, 0, 0, AuditStatus.COMPLETE
    )
    ind = IndustryStrengthAudit(date(2026, 8, 20), 30, AuditStatus.COMPLETE)
    dup = DuplicateAudit(0, 0, 0, 0, 0, AuditStatus.COMPLETE)

    report = DailyDataAuditReport(
        target_date=date(2026, 8, 20),
        is_trading_day=True,
        day_type="TRADING_DAY",
        security_master=sec,
        twse_daily=twse,
        tpex_daily=tpex,
        market_spot=spot,
        derivatives=deriv,
        technicals=tech,
        industry_strength=ind,
        duplicates=dup,
        overall_status=AuditStatus.COMPLETE,
    )
    print_human_daily_report(report)
    out1 = capsys.readouterr().out
    assert "MARKET DATA QUALITY AUDIT: 2026-08-20 (TRADING_DAY)" in out1

    gap = HistoricalGapAudit(
        market="TWSE",
        start_date=date(2021, 8, 11),
        end_date=date(2026, 8, 20),
        total_weekdays=1300,
        trading_sessions=1211,
        holiday_sessions=89,
        anomalous_sessions=0,
        anomalies=[],
        status=AuditStatus.COMPLETE,
    )
    print_human_gap_report(gap)
    out2 = capsys.readouterr().out
    assert "HISTORICAL GAP AUDIT: TWSE" in out2
    assert "No anomalous coverage gaps found" in out2
