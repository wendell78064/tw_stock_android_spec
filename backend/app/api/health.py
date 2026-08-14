from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import database_session, readiness_checker, redis_client
from app.services.ai_grounding import FakeAIProvider
from app.services.production_readiness import ProductionReadinessService
from app.services.push_notifications import FakePushProvider
from app.services.readiness import ReadinessChecker

router = APIRouter()


@router.get("/health", operation_id="health_check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", operation_id="readiness_check")
async def ready(
    session: Annotated[AsyncSession, Depends(database_session)],
    redis: Annotated[Any, Depends(redis_client)] = None,
) -> dict[str, Any]:
    service = ProductionReadinessService(
        session=session,
        ai_provider=FakeAIProvider(),
        push_provider=FakePushProvider(),
        redis_client=redis,
    )
    return await service.check_health()
