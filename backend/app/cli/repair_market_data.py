import argparse
import asyncio
import json
from datetime import date
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.core.settings import get_settings
from app.domain.audit import (
    AuditFinding,
    AuditStatus,
    PrecisionRepairResult,
)
from app.services.precision_repair import PrecisionRepairService


def print_human_repair_result(result: PrecisionRepairResult) -> None:
    sep = "=" * 68
    sub_sep = "-" * 68
    print("\n" + sep)
    print(" PRECISION MARKET DATA REPAIR REPORT")
    print(sep)
    dec = result.decision
    print(f"Finding ID:      {result.finding_id}")
    print(f"Decision:        {dec.outcome.value}")
    print(f"Decision Reason: {dec.reason}")
    if dec.scope:
        sc = dec.scope
        print(f"Scope Type:      {sc.scope_type.value}")
        print(f"Dataset:         {sc.dataset}")
        if sc.target_date:
            print(f"Target Date:     {sc.target_date.isoformat()}")
        if sc.start_date and sc.end_date:
            print(f"Date Range:      {sc.start_date.isoformat()} -> {sc.end_date.isoformat()}")
        if sc.market:
            print(f"Market:          {sc.market}")
        if sc.security_code:
            print(f"Security:        {sc.security_code}")
    print(sub_sep)
    print(f"Executed:        {'YES' if result.executed else 'NO'}")
    print(f"Status Before:   {result.status_before.value}")
    print(f"Status After:    {result.status_after.value}")
    print(f"Records Ins:     {result.repaired_records_inserted}")
    print(f"Records Upd:     {result.repaired_records_updated}")
    if result.ingestion_run_id:
        print(f"Run ID:          {result.ingestion_run_id}")
    if result.error:
        print(f"Error:           {result.error}")
    print(sep + "\n")


async def run_repair(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis_url, decode_responses=True) if not args.no_lock else None

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    start_date = date.fromisoformat(args.start) if args.start else None
    end_date = date.fromisoformat(args.end) if args.end else None

    finding_id = args.finding_id or f"finding-{uuid4().hex[:8]}"

    finding = AuditFinding(
        finding_id=finding_id,
        dataset=args.dataset,
        target_date=target_date,
        audit_status=(
            AuditStatus.PARTIAL if not args.initial_status else AuditStatus(args.initial_status)
        ),
        market=args.market,
        security_code=args.code,
        start_date=start_date,
        end_date=end_date,
        reason=args.reason,
    )

    calendar = WeekendOnlyCalendar()

    try:
        async with factory() as session:
            service = PrecisionRepairService(
                session=session,
                calendar=calendar,
                provider_mode=args.provider,
                redis=redis,
            )
            result = await service.execute_repair(finding, skip_lock=args.no_lock)

            if args.format == "json":
                print(json.dumps(result.to_dict(), indent=2))
            else:
                print_human_repair_result(result)
    finally:
        if redis:
            await redis.aclose()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Precision Data Repair CLI")
    parser.add_argument(
        "--dataset", required=True, help="Dataset to repair, e.g. DAILY_PRICES, MARKET_BREADTH"
    )
    parser.add_argument("--date", help="Target date YYYY-MM-DD")
    parser.add_argument("--market", choices=["TWSE", "TPEX"], help="Market code")
    parser.add_argument("--code", help="Security code e.g. 2330")
    parser.add_argument("--start", help="Start date YYYY-MM-DD for range")
    parser.add_argument("--end", help="End date YYYY-MM-DD for range")
    parser.add_argument("--finding-id", help="Optional finding ID")
    parser.add_argument(
        "--initial-status", choices=[s.value for s in AuditStatus], help="Status before repair"
    )
    parser.add_argument("--reason", help="Audit finding reason")
    parser.add_argument(
        "--provider", choices=["official", "fake"], default="official", help="Provider mode"
    )
    parser.add_argument("--no-lock", action="store_true", help="Skip distributed job lock")
    parser.add_argument(
        "--format", choices=["human", "json"], default="human", help="Output format"
    )

    args = parser.parse_args()
    asyncio.run(run_repair(args))


if __name__ == "__main__":
    main()
