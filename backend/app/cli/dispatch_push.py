"""Explicit bounded outbox drain; does not create events or alter alert eligibility."""

import asyncio

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fcm_push import FcmPushProvider
from app.core.settings import get_settings
from app.repositories.push_models import PushDeliveryModel, PushEventModel
from app.services.push_notifications import PushNotificationService


async def run():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            events = (await session.scalars(select(PushEventModel).where(
                PushEventModel.user_id.is_not(None),
                ~exists(select(PushDeliveryModel.id).where(
                    PushDeliveryModel.event_id == PushEventModel.id)),
            ).order_by(PushEventModel.created_at).limit(100))).all()
            service = PushNotificationService(session, FcmPushProvider(settings))
            for event in events:
                await service.deliver_event(event, settings.fcm_max_retries)
            print(f"EVENTS_PROCESSED={len(events)}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
