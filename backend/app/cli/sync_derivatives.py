import argparse
import asyncio
from datetime import date, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fake_derivatives import FakeDerivativesDataProvider
from app.adapters.taifex import OfficialTaifexProvider
from app.core.settings import get_settings
from app.repositories.sql_derivatives import SqlDerivativesRepository
from app.services.derivatives_ingestion import DERIVATIVE_DATASETS, DerivativesIngestionService


async def run(provider_name: str, start: date, end: date, only: set[str] | None = None):
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = (
        FakeDerivativesDataProvider() if provider_name == "fake" else OfficialTaifexProvider()
    )
    current = start
    while current <= end:
        if current.weekday() < 5:
            for dataset in DERIVATIVE_DATASETS:
                if only and dataset not in only:
                    continue
                try:
                    async with factory() as session:
                        result = await DerivativesIngestionService(
                            session, SqlDerivativesRepository(session)
                        ).synchronize_dataset(provider, dataset, current)
                        print(
                            f"{current} {provider.source_code} {dataset} {result.status} "
                            f"fetched={result.fetched_count} inserted={result.inserted_count} "
                            f"updated={result.updated_count} rejected={result.rejected_count}"
                        )
                except Exception as error:
                    print(
                        f"{current} {provider.source_code} {dataset} FAILED: {error}"
                    )
        current += timedelta(days=1)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        keys = []
        for pattern in ("futures:*", "options:*", "vix:*", "market:overview:*"):
            keys.extend([key async for key in redis.scan_iter(pattern)])
        if keys:
            await redis.delete(*set(keys))
    finally:
        await redis.aclose()
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("fake", "taifex"), default="fake")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--dataset", action="append", choices=tuple(DERIVATIVE_DATASETS))
    args = parser.parse_args()
    target = args.date or date(2026, 8, 7)
    asyncio.run(
        run(
            args.provider,
            args.start or target,
            args.end or target,
            set(args.dataset) if args.dataset else None,
        )
    )


if __name__ == "__main__":
    main()
