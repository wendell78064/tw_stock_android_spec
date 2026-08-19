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


from datetime import date, timedelta


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
    calendar = WeekendOnlyCalendar()
    start_d = date.fromisoformat(args.start) if args.start else None
    end_d = date.fromisoformat(args.end) if args.end else None
    single_d = date.fromisoformat(args.date) if args.date else None

    if start_d and end_d and args.provider == "official":
        cur = start_d
        target_dates: list[date | None] = []
        while cur <= end_d:
            if calendar.is_trading_day(cur):
                target_dates.append(cur)
            cur += timedelta(days=1)
    elif single_d:
        target_dates = [single_d]
    else:
        target_dates = [None]

    try:
        for current_date in target_dates:
            for provider in providers:
                async with factory() as session:
                    repository = SqlPriceRepository(session)
                    run_result = await DailyPriceIngestionService(
                        session, repository, calendar
                    ).synchronize(
                        provider,
                        trade_date=current_date,
                        security=security,
                        start_date=start_d if args.provider == "fake" else None,
                        end_date=end_d if args.provider == "fake" else None,
                    )
                    date_str = f" {current_date.isoformat()}" if current_date else ""
                    print(
                        f"{run_result.provider}{date_str} {run_result.status} "
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
