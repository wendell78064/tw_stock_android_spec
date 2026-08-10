import argparse
import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.core.settings import get_settings
from app.domain.pricing import PriceBasis, SecurityKey
from app.domain.security import MarketCode
from app.repositories.sql_price import SqlPriceRepository
from app.services.daily_price_ingestion import (
    DailyPriceIngestionService,
    TechnicalCalculationService,
)


async def run(args: argparse.Namespace) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    security = (
        SecurityKey(MarketCode(args.market), args.code) if args.code and args.market else None
    )
    providers = (
        [FakeMarketDataProvider()]
        if args.provider == "fake"
        else [TwseSecurityProvider(), TpexSecurityProvider()]
    )
    try:
        for provider in providers:
            async with factory() as session:
                repository = SqlPriceRepository(session)
                run_result = await DailyPriceIngestionService(
                    session, repository, WeekendOnlyCalendar()
                ).synchronize(
                    provider,
                    trade_date=date.fromisoformat(args.date) if args.date else None,
                    security=security,
                    start_date=date.fromisoformat(args.start) if args.start else None,
                    end_date=date.fromisoformat(args.end) if args.end else None,
                )
                print(
                    f"{run_result.provider} {run_result.status} "
                    f"fetched={run_result.fetched_count} "
                    f"inserted={run_result.inserted_count} "
                    f"updated={run_result.updated_count} "
                    f"rejected={run_result.rejected_count}"
                )
                if security:
                    calculator = TechnicalCalculationService(repository)
                    for basis in PriceBasis:
                        count = await calculator.recalculate(security, basis)
                        print(f"{security.market}:{security.code} {basis} technicals={count}")
                    await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("fake", "official"), default="fake")
    parser.add_argument("--date")
    parser.add_argument("--code")
    parser.add_argument("--market", choices=("TWSE", "TPEX"))
    parser.add_argument("--start")
    parser.add_argument("--end")
    args = parser.parse_args()
    if bool(args.code) != bool(args.market):
        parser.error("--code and --market are required together")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
