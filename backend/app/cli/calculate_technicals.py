import argparse
import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.domain.pricing import PriceBasis, SecurityKey
from app.domain.security import MarketCode, SecurityType
from app.repositories.models import MarketModel, SecurityModel
from app.repositories.sql_price import SqlPriceRepository
from app.services.daily_price_ingestion import TechnicalCalculationService

DEFAULT_BATCH_SIZE = 100


async def list_target_securities(
    session,
    market_filter: str | None = None,
    code_filter: str | None = None,
) -> list[SecurityKey]:
    stmt = (
        select(MarketModel.code, SecurityModel.code)
        .join(MarketModel, MarketModel.id == SecurityModel.market_id)
        .where(
            SecurityModel.is_active.is_(True),
            SecurityModel.security_type == SecurityType.COMMON_STOCK.value,
        )
    )
    if market_filter:
        stmt = stmt.where(MarketModel.code == market_filter.upper())
    if code_filter:
        stmt = stmt.where(SecurityModel.code == code_filter.strip())
    stmt = stmt.order_by(MarketModel.code, SecurityModel.code)
    rows = (await session.execute(stmt)).all()
    return [SecurityKey(MarketCode(m), c) for m, c in rows]


async def run(
    target_date: date | None = None,
    market_filter: str | None = None,
    code_filter: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, int]:
    del target_date
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    total_securities = 0
    succeeded = 0
    failed = 0
    total_snapshots = 0

    try:
        async with factory() as session:
            securities = await list_target_securities(session, market_filter, code_filter)
        total_securities = len(securities)
        print(f"Starting technical calculations for {total_securities} active common stocks (batch_size={batch_size})...")

        for i in range(0, total_securities, batch_size):
            batch = securities[i : i + batch_size]
            async with factory() as session:
                repo = SqlPriceRepository(session)
                service = TechnicalCalculationService(repo)
                for sec in batch:
                    try:
                        for basis in PriceBasis:
                            count = await service.recalculate(sec, basis)
                            total_snapshots += count
                        succeeded += 1
                    except Exception as err:
                        failed += 1
                        print(f"Error calculating technicals for {sec.market}:{sec.code}: {err}")
                await session.commit()
            print(f"Processed batch {i // batch_size + 1}/{(total_securities + batch_size - 1) // batch_size} ({min(i + batch_size, total_securities)}/{total_securities})")
    finally:
        await engine.dispose()

    summary = {
        "total": total_securities,
        "succeeded": succeeded,
        "failed": failed,
        "snapshots": total_snapshots,
    }
    print(
        f"Technical calculation finished: total={total_securities} "
        f"succeeded={succeeded} failed={failed} snapshots={total_snapshots}"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate Technical Indicators for Active Common Stocks")
    parser.add_argument("--date", type=date.fromisoformat, help="Target date YYYY-MM-DD")
    parser.add_argument("--market", choices=("TWSE", "TPEX"), help="Market filter")
    parser.add_argument("--code", help="4-digit stock code filter")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Batch size (default: 100)")
    args = parser.parse_args()
    asyncio.run(run(args.date, args.market, args.code, args.batch_size))


if __name__ == "__main__":
    main()
