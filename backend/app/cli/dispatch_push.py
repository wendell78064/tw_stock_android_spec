"""Explicit bounded outbox drain; does not create events or alter alert eligibility."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fcm_push import FcmPushProvider
from app.core.settings import get_settings
from app.services.push_notifications import drain_outbox


async def run():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            processed = await drain_outbox(
                session=session,
                provider=FcmPushProvider(settings),
                batch_size=settings.fcm_dispatch_batch_size,
                max_retries=settings.fcm_max_retries,
            )
            print(f"EVENTS_PROCESSED={processed}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
