import argparse
import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.core.settings import get_settings
from app.repositories.sql_security import SqlSecurityRepository
from app.services.security_ingestion import SecurityIngestionService


async def run(provider_name: str) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    providers = (
        [FakeMarketDataProvider()]
        if provider_name == "fake"
        else [TwseSecurityProvider(), TpexSecurityProvider()]
    )
    try:
        for provider in providers:
            async with factory() as session:
                runs = await SecurityIngestionService(
                    session, SqlSecurityRepository(session)
                ).synchronize(provider)
                for item in runs:
                    print(
                        f"{item.provider} {item.status} fetched={item.fetched_count} "
                        f"inserted={item.inserted_count} updated={item.updated_count}"
                    )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize TWSE/TPEx common-stock masters")
    parser.add_argument("--provider", choices=("fake", "official"), default="fake")
    args = parser.parse_args()
    asyncio.run(run(args.provider))


if __name__ == "__main__":
    main()
