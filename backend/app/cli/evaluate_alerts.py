import argparse
import asyncio
from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.settings import get_settings
from app.repositories.sql_alert import SqlAlertRepository
from app.services.alerts import AlertEvaluationService


async def run(value: str | None) -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await AlertEvaluationService(SqlAlertRepository(session)).evaluate(
                date.fromisoformat(value) if value else None
            )
            print(result)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date")
    args = parser.parse_args()
    asyncio.run(run(args.date))


if __name__ == "__main__":
    main()
