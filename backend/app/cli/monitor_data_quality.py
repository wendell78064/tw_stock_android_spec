import argparse
import asyncio
import json
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.domain.monitoring import MonitoringRunResult
from app.services.data_quality_monitoring import DataQualityMonitoringService


def print_human_monitoring_result(res: MonitoringRunResult) -> None:
    sep = "=" * 68
    sub_sep = "-" * 68
    print("\n" + sep)
    print(f" DATA QUALITY MONITORING RESULT: {res.target_date.isoformat()}")
    print(sep)
    print(f"Anomalies Detected:      {res.anomalies_detected}")
    print(f"Anomalies Active:        {res.anomalies_active}")
    print(f"Anomalies New:           {res.anomalies_new}")
    print(f"Anomalies Resolved:      {res.anomalies_resolved}")
    print(f"Notifications Created:   {res.notifications_created}")
    print(f"Notifications Suppressed:{res.notifications_suppressed}")
    print(sub_sep)

    if not res.notifications:
        print(">> Status: ALL CLEAR. Zero notifications emitted (silent).")
    else:
        print(">> Emitted Notifications Summary:")
        for n in res.notifications:
            prefix = "[RESOLVED]" if n.is_resolution else f"[{n.severity.value}]"
            print(f"  * {prefix:<11} {n.title}")
            print(f"    Body: {n.body}")
            print(f"    Key:  {n.dedupe_key}")

    print(sep + "\n")


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with factory() as session:
            service = DataQualityMonitoringService(
                session=session,
                cooldown_hours=args.cooldown_hours,
            )
            target_date = args.date or date.today()
            res = await service.evaluate_date(target_date)

            if args.json:
                print(json.dumps(res.to_dict(), indent=2))
            else:
                print_human_monitoring_result(res)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="TW Market Ledger Data Quality Monitoring CLI")
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Target date to evaluate YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--cooldown-hours",
        type=int,
        default=24,
        help="Cooldown window in hours for duplicate notifications (default: 24)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as structured JSON",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
