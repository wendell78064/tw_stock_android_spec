import argparse
import asyncio
import json
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.domain.audit import DailyDataAuditReport, HistoricalGapAudit
from app.services.data_quality_audit import DataQualityAuditService


def print_human_daily_report(report: DailyDataAuditReport) -> None:
    sep = "=" * 68
    sub_sep = "-" * 68
    print("\n" + sep)
    print(f" MARKET DATA QUALITY AUDIT: {report.target_date.isoformat()} ({report.day_type})")
    print(sep)

    print(f"Overall Status: {report.overall_status.value}")
    print(f"Trading Day:    {'YES' if report.is_trading_day else 'NO'}")
    print(sub_sep)

    # 1. SECURITY MASTER
    sec = report.security_master
    print(
        f"{'SECURITY_MASTER':<22} {sec.status.value:<12} "
        f"total={sec.total_securities} active_common={sec.active_common_stocks} "
        f"(TWSE={sec.twse_common_stocks}, TPEX={sec.tpex_common_stocks}) "
        f"dup={sec.duplicate_count}"
    )

    # 2. TWSE DAILY
    twse = report.twse_daily
    twse_cov = f"{twse.coverage_ratio * 100:.1f}%"
    print(
        f"{'TWSE_DAILY':<22} {twse.status.value:<12} "
        f"rows={twse.rows_with_price}/{twse.expected_eligible} ({twse_cov}) "
        f"trade={twse.trading_rows} no_trade={twse.suspended_or_no_trade_rows} "
        f"dup={twse.duplicate_count}"
    )

    # 3. TPEX DAILY
    tpex = report.tpex_daily
    tpex_cov = f"{tpex.coverage_ratio * 100:.1f}%"
    print(
        f"{'TPEX_DAILY':<22} {tpex.status.value:<12} "
        f"rows={tpex.rows_with_price}/{tpex.expected_eligible} ({tpex_cov}) "
        f"trade={tpex.trading_rows} no_trade={tpex.suspended_or_no_trade_rows} "
        f"dup={tpex.duplicate_count}"
    )

    # 4. MARKET SPOT
    spot = report.market_spot
    print(
        f"{'MARKET_SPOT':<22} {spot.status.value:<12} "
        f"breadth={spot.market_breadth_rows} margin={spot.margin_trading_rows} "
        f"lending={spot.securities_lending_rows} inst={spot.institutional_spot_rows} "
        f"dup={spot.duplicate_count}"
    )

    # 5. DERIVATIVES
    print(f"{'DERIVATIVES (TAIFEX)':<22}")
    for d in report.derivatives:
        extra = f" ({d.note})" if d.note else ""
        print(f"  └─ {d.dataset:<22} {d.status.value:<12} rows={d.row_count}{extra}")

    # 6. TECHNICALS
    tech = report.technicals
    snap_date_str = tech.snapshot_date.isoformat() if tech.snapshot_date else "None"
    print(
        f"{'TECHNICALS':<22} {tech.status.value:<12} "
        f"snapshots={tech.snapshots_count}/{tech.active_stocks} "
        f"(as_of={snap_date_str}) stale={tech.stale_count} "
        f"ma240_valid={tech.ma240_valid_count}/{tech.ma240_eligible_count} "
        f"dup={tech.duplicate_count}"
    )

    # 7. INDUSTRY STRENGTH
    ind = report.industry_strength
    ind_date_str = ind.snapshot_date.isoformat() if ind.snapshot_date else "None"
    print(
        f"{'INDUSTRY_STRENGTH':<22} {ind.status.value:<12} "
        f"snapshots={ind.snapshot_count} (as_of={ind_date_str})"
    )

    # 8. DUPLICATES
    dup = report.duplicates
    print(
        f"{'DUPLICATE_CHECK':<22} {dup.status.value:<12} "
        f"sec={dup.duplicate_securities} price={dup.duplicate_daily_prices} "
        f"tech={dup.duplicate_technical_snapshots} spot={dup.duplicate_market_spot} "
        f"deriv={dup.duplicate_derivatives}"
    )

    print(sep + "\n")


def print_human_gap_report(report: HistoricalGapAudit) -> None:
    sep = "=" * 68
    sub_sep = "-" * 68
    print("\n" + sep)
    date_range = f"{report.start_date.isoformat()} ~ {report.end_date.isoformat()}"
    print(f" HISTORICAL GAP AUDIT: {report.market} ({date_range})")
    print(sep)

    print(f"Status:             {report.status.value}")
    print(f"Total Weekdays:     {report.total_weekdays}")
    print(f"Trading Sessions:   {report.trading_sessions}")
    print(f"Holiday Sessions:   {report.holiday_sessions}")
    print(f"Anomalous Sessions: {report.anomalous_sessions}")
    print(sub_sep)

    if not report.anomalies:
        print(">> No anomalous coverage gaps found across history. All sessions COMPLETE.")
    else:
        print(">> Anomalous Sessions Summary:")
        for anom in report.anomalies[:25]:  # Bounded output
            anom_dt = anom.trade_date.isoformat()
            cov_pct = f"{anom.coverage_ratio * 100:.1f}%"
            print(
                f"  - {anom_dt} {anom.market:<6} actual={anom.actual}/{anom.expected} "
                f"({cov_pct}) reason: {anom.reason}"
            )
        if len(report.anomalies) > 25:
            print(f"  ... and {len(report.anomalies) - 25} more anomalous sessions.")

    print(sep + "\n")


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            service = DataQualityAuditService(session)

            if args.start and args.end:
                gap_report = await service.audit_historical_gap(
                    start_date=args.start,
                    end_date=args.end,
                    market=args.market,
                )
                if args.json:
                    from dataclasses import asdict
                    data = asdict(gap_report)
                    data["start_date"] = data["start_date"].isoformat()
                    data["end_date"] = data["end_date"].isoformat()
                    for item in data.get("anomalies", []):
                        item["trade_date"] = item["trade_date"].isoformat()
                    print(json.dumps(data, indent=2))
                else:
                    print_human_gap_report(gap_report)
            else:
                target_date = args.date or date.today()
                daily_report = await service.audit_date(target_date)
                if args.json:
                    print(json.dumps(daily_report.to_dict(), indent=2))
                else:
                    print_human_daily_report(daily_report)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TW Market Ledger Production Data Quality Audit"
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Target date for daily audit YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        help="Start date for historical gap audit YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        type=date.fromisoformat,
        help="End date for historical gap audit YYYY-MM-DD",
    )
    parser.add_argument(
        "--market",
        choices=("TWSE", "TPEX"),
        help="Filter historical gap audit by market",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in structured JSON format",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
