import argparse
import asyncio
import time
from dataclasses import dataclass
from datetime import date
from typing import Literal

import httpx
from redis.asyncio import Redis
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.adapters.fake_derivatives import FakeDerivativesDataProvider
from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.official_spot import OfficialTpexProvider, OfficialTwseProvider
from app.adapters.taifex import OfficialTaifexProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.cli import calculate_technicals
from app.core.job_lock import distributed_job_lock
from app.core.settings import get_settings
from app.repositories.sql_derivatives import SqlDerivativesRepository
from app.repositories.sql_market_spot import SqlMarketSpotRepository
from app.repositories.sql_price import SqlPriceRepository
from app.repositories.sql_security import SqlSecurityRepository
from app.services.daily_price_ingestion import DailyPriceIngestionService
from app.services.derivatives_ingestion import DERIVATIVE_DATASETS, DerivativesIngestionService
from app.services.industry_strength_calculation import IndustryStrengthCalculationService
from app.services.market_spot_ingestion import DATASETS, MarketSpotIngestionService
from app.services.security_ingestion import SecurityIngestionService

StepStatus = Literal["SUCCEEDED", "PARTIAL", "FAILED", "SKIPPED", "NO_DATA", "DEGRADED"]


@dataclass
class StepResult:
    name: str
    status: StepStatus
    duration: float
    summary: str
    error: str | None = None


async def execute_step_with_retry(step_fn, max_retries: int = 1, backoff_seconds: float = 2.0):
    attempt = 0
    while True:
        try:
            return await step_fn()
        except (httpx.HTTPError, TimeoutError, ConnectionError):
            attempt += 1
            if attempt > max_retries:
                raise
            await asyncio.sleep(backoff_seconds)


class DailyPipelineRunner:
    def __init__(self, target_date: date, provider_type: str = "official"):
        self.target_date = target_date
        self.provider_type = provider_type
        self.settings = get_settings()
        self.async_engine = create_async_engine(self.settings.database_url)
        self.async_factory = async_sessionmaker(self.async_engine, expire_on_commit=False)
        self.calendar = WeekendOnlyCalendar()

    async def run(self, skip_lock: bool = False) -> list[StepResult]:
        if self.target_date.weekday() >= 5:
            print(f"Target date {self.target_date} is a weekend. Skipping pipeline.")
            return [
                StepResult(
                    name="ALL_STEPS",
                    status="SKIPPED",
                    duration=0.0,
                    summary="Weekend non-trading day",
                )
            ]

        redis = Redis.from_url(self.settings.redis_url, decode_responses=True)
        try:
            if skip_lock:
                return await self._run_steps(redis)
            async with distributed_job_lock(redis, "daily-pipeline", ttl_seconds=3600) as acquired:
                if not acquired:
                    print(
                        "ALREADY_RUNNING: Another instance of daily pipeline is currently running."
                    )
                    return [
                        StepResult(
                            name="JOB_LOCK",
                            status="SKIPPED",
                            duration=0.0,
                            summary="Pipeline lock already held by another runner",
                        )
                    ]
                return await self._run_steps(redis)
        finally:
            await redis.aclose()
            await self.async_engine.dispose()

    async def _run_steps(self, redis: Redis) -> list[StepResult]:
        steps: list[StepResult] = []
        overall_start = time.monotonic()

        # Step 1: SECURITY_MASTER
        step1 = await self._run_security_master()
        steps.append(step1)

        # Step 2: DAILY_PRICES
        step2, daily_has_data = await self._run_daily_prices()
        steps.append(step2)

        # Step 3: MARKET_SPOT
        step3 = await self._run_market_spot(redis)
        steps.append(step3)

        # Step 4: DERIVATIVES
        step4 = await self._run_derivatives(redis)
        steps.append(step4)

        # Step 5: TECHNICALS
        step5 = await self._run_technicals(daily_has_data)
        steps.append(step5)

        # Step 6: INDUSTRY_STRENGTH
        step6 = await self._run_industry_strength(daily_has_data)
        steps.append(step6)

        total_duration = time.monotonic() - overall_start
        self._print_summary(steps, total_duration)
        return steps

    async def _run_security_master(self) -> StepResult:
        start = time.monotonic()
        try:
            providers = (
                [FakeMarketDataProvider()]
                if self.provider_type == "fake"
                else [TwseSecurityProvider(), TpexSecurityProvider()]
            )
            total_fetched = total_inserted = total_updated = 0
            for provider in providers:
                async with self.async_factory() as session:
                    runs = await execute_step_with_retry(
                        lambda p=provider, s=session: SecurityIngestionService(
                            s, SqlSecurityRepository(s)
                        ).synchronize(p)
                    )
                    for item in runs:
                        total_fetched += item.fetched_count
                        total_inserted += item.inserted_count
                        total_updated += item.updated_count
            return StepResult(
                name="SECURITY_MASTER",
                status="SUCCEEDED",
                duration=time.monotonic() - start,
                summary=(
                    f"fetched={total_fetched} "
                    f"inserted={total_inserted} "
                    f"updated={total_updated}"
                ),
            )
        except Exception as error:
            return StepResult(
                name="SECURITY_MASTER",
                status="DEGRADED",
                duration=time.monotonic() - start,
                summary="Security Master update failed; using existing master",
                error=str(error),
            )

    async def _run_daily_prices(self) -> tuple[StepResult, bool]:
        start = time.monotonic()
        try:
            providers = (
                [FakeMarketDataProvider()]
                if self.provider_type == "fake"
                else [TwseSecurityProvider(), TpexSecurityProvider()]
            )
            total_fetched = total_inserted = total_updated = total_rejected = 0
            for provider in providers:
                async with self.async_factory() as session:
                    repo = SqlPriceRepository(session)
                    service = DailyPriceIngestionService(session, repo, self.calendar)
                    run_result = await execute_step_with_retry(
                        lambda srv=service, p=provider: srv.synchronize(
                            p, trade_date=self.target_date
                        )
                    )
                    total_fetched += run_result.fetched_count
                    total_inserted += run_result.inserted_count
                    total_updated += run_result.updated_count
                    total_rejected += run_result.rejected_count

            has_data = (total_inserted + total_updated) > 0
            status: StepStatus = "SUCCEEDED" if total_rejected == 0 else "PARTIAL"
            if not has_data and total_fetched == 0:
                status = "NO_DATA"

            return (
                StepResult(
                    name="DAILY_PRICES",
                    status=status,
                    duration=time.monotonic() - start,
                    summary=(
                        f"fetched={total_fetched} "
                        f"inserted={total_inserted} "
                        f"updated={total_updated} "
                        f"rejected={total_rejected}"
                    ),
                ),
                has_data,
            )
        except Exception as error:
            return (
                StepResult(
                    name="DAILY_PRICES",
                    status="FAILED",
                    duration=time.monotonic() - start,
                    summary="Daily prices synchronization failed",
                    error=str(error),
                ),
                False,
            )

    async def _run_market_spot(self, redis: Redis) -> StepResult:
        start = time.monotonic()
        try:
            providers = (
                [FakeMarketDataProvider()]
                if self.provider_type == "fake"
                else [OfficialTwseProvider(), OfficialTpexProvider()]
            )
            succeeded_datasets = 0
            total_datasets = 0
            for provider in providers:
                for dataset in DATASETS:
                    total_datasets += 1
                    try:
                        async with self.async_factory() as session:
                            repo = SqlMarketSpotRepository(session)
                            service = MarketSpotIngestionService(session, repo)
                            await execute_step_with_retry(
                                lambda srv=service, p=provider, ds=dataset: srv.synchronize_dataset(
                                    p, ds, self.target_date
                                )
                            )
                            succeeded_datasets += 1
                    except Exception as err:
                        print(f"Market spot {dataset} failed on {provider}: {err}")

            # Clear cache
            keys = [k async for k in redis.scan_iter("market:overview:*")]
            if keys:
                await redis.delete(*keys)

            status: StepStatus = "SUCCEEDED" if succeeded_datasets == total_datasets else "PARTIAL"
            return StepResult(
                name="MARKET_SPOT",
                status=status,
                duration=time.monotonic() - start,
                summary=f"datasets={succeeded_datasets}/{total_datasets} succeeded",
            )
        except Exception as error:
            return StepResult(
                name="MARKET_SPOT",
                status="FAILED",
                duration=time.monotonic() - start,
                summary="Market spot synchronization failed",
                error=str(error),
            )

    async def _run_derivatives(self, redis: Redis) -> StepResult:
        start = time.monotonic()
        try:
            provider = (
                FakeDerivativesDataProvider()
                if self.provider_type == "fake"
                else OfficialTaifexProvider()
            )
            succeeded_datasets = 0
            total_datasets = len(DERIVATIVE_DATASETS)
            for dataset in DERIVATIVE_DATASETS:
                try:
                    async with self.async_factory() as session:
                        repo = SqlDerivativesRepository(session)
                        service = DerivativesIngestionService(session, repo)
                        await execute_step_with_retry(
                            lambda srv=service, prov=provider, ds=dataset: (
                                srv.synchronize_dataset(prov, ds, self.target_date)
                            )
                        )
                        succeeded_datasets += 1
                except Exception as err:
                    print(f"Derivatives {dataset} failed: {err}")

            keys = []
            for pattern in ("futures:*", "options:*", "vix:*", "market:overview:*"):
                keys.extend([k async for k in redis.scan_iter(pattern)])
            if keys:
                await redis.delete(*set(keys))

            status: StepStatus = "SUCCEEDED" if succeeded_datasets == total_datasets else "PARTIAL"
            return StepResult(
                name="DERIVATIVES",
                status=status,
                duration=time.monotonic() - start,
                summary=f"datasets={succeeded_datasets}/{total_datasets} succeeded",
            )
        except Exception as error:
            return StepResult(
                name="DERIVATIVES",
                status="FAILED",
                duration=time.monotonic() - start,
                summary="Derivatives synchronization failed",
                error=str(error),
            )

    async def _run_technicals(self, daily_has_data: bool) -> StepResult:
        start = time.monotonic()
        if not daily_has_data and self.provider_type == "official":
            return StepResult(
                name="TECHNICALS",
                status="SKIPPED",
                duration=0.0,
                summary="Skipped due to no daily price data",
            )
        try:
            summary = await calculate_technicals.run(
                target_date=self.target_date, batch_size=100
            )
            status: StepStatus = "SUCCEEDED" if summary["failed"] == 0 else "PARTIAL"
            return StepResult(
                name="TECHNICALS",
                status=status,
                duration=time.monotonic() - start,
                summary=(
                    f"total={summary['total']} "
                    f"succeeded={summary['succeeded']} "
                    f"failed={summary['failed']} "
                    f"snapshots={summary['snapshots']}"
                ),
            )
        except Exception as error:
            return StepResult(
                name="TECHNICALS",
                status="FAILED",
                duration=time.monotonic() - start,
                summary="Technical indicators calculation failed",
                error=str(error),
            )

    async def _run_industry_strength(self, daily_has_data: bool) -> StepResult:
        start = time.monotonic()
        if not daily_has_data and self.provider_type == "official":
            return StepResult(
                name="INDUSTRY_STRENGTH",
                status="SKIPPED",
                duration=0.0,
                summary="Skipped due to no daily price data",
            )
        try:
            sync_url = self.settings.database_url.replace("+asyncpg", "").replace("+psycopg", "")
            sync_engine = create_engine(sync_url)
            SyncSession = sessionmaker(bind=sync_engine)
            with SyncSession() as session:
                calc_service = IndustryStrengthCalculationService(session)
                res = calc_service.calculate_for_date(self.target_date)
            return StepResult(
                name="INDUSTRY_STRENGTH",
                status="SUCCEEDED",
                duration=time.monotonic() - start,
                summary=f"inserted={res['inserted']} updated={res['updated']}",
            )
        except Exception as error:
            return StepResult(
                name="INDUSTRY_STRENGTH",
                status="FAILED",
                duration=time.monotonic() - start,
                summary="Industry strength calculation failed",
                error=str(error),
            )

    def _print_summary(self, steps: list[StepResult], total_duration: float) -> None:
        print("\n" + "=" * 64)
        print(f"DAILY PIPELINE SUMMARY: {self.target_date.isoformat()}")
        print("=" * 64)
        statuses = [s.status for s in steps]
        overall: StepStatus = "SUCCEEDED"
        if any(s == "FAILED" for s in statuses):
            overall = "FAILED"
        elif any(s in ("PARTIAL", "DEGRADED") for s in statuses):
            overall = "PARTIAL"
        elif all(s == "SKIPPED" for s in statuses):
            overall = "SKIPPED"

        for step in steps:
            dur_str = f"({step.duration:.1f}s)"
            print(f"{step.name:<20} {step.status:<10} {dur_str:<8} {step.summary}")
            if step.error:
                print(f"  └─ Error: {step.error}")

        print("-" * 64)
        print(f"OVERALL STATUS:      {overall:<10} (total duration: {total_duration:.1f}s)")
        print("=" * 64 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TW Market Ledger Production Daily Pipeline"
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--provider",
        choices=("official", "fake"),
        default="official",
        help="Provider source",
    )
    parser.add_argument(
        "--skip-lock",
        action="store_true",
        help="Skip distributed Redis job lock check",
    )
    args = parser.parse_args()
    target_d = args.date or date.today()
    runner = DailyPipelineRunner(target_d, args.provider)
    asyncio.run(runner.run(skip_lock=args.skip_lock))


if __name__ == "__main__":
    main()
