import argparse
import asyncio
from datetime import date, timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.official_spot import OfficialTpexProvider, OfficialTwseProvider
from app.core.settings import get_settings
from app.repositories.sql_market_spot import SqlMarketSpotRepository
from app.services.market_spot_ingestion import DATASETS, MarketSpotIngestionService


async def run(provider_name: str, start: date, end: date) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    provider = {
        "fake": FakeMarketDataProvider,
        "twse": OfficialTwseProvider,
        "tpex": OfficialTpexProvider,
    }[provider_name]()
    current = start
    while current <= end:
        if current.weekday() < 5:
            for dataset in DATASETS:
                async with factory() as session:
                    result = await MarketSpotIngestionService(
                        session, SqlMarketSpotRepository(session)
                    ).synchronize_dataset(provider, dataset, current)
                    print(
                        f"{current} {dataset} {result.status} fetched={result.fetched_count} "
                        f"inserted={result.inserted_count} updated={result.updated_count}"
                    )
        current += timedelta(days=1)
    redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        keys = [key async for key in redis.scan_iter("market:overview:*")]
        if keys:
            await redis.delete(*keys)
    finally:
        await redis.aclose()
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("fake", "twse", "tpex"), default="fake")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    args = parser.parse_args()
    target = args.date or date(2026, 8, 7)
    asyncio.run(run(args.provider, args.start or target, args.end or target))


if __name__ == "__main__":
    main()
