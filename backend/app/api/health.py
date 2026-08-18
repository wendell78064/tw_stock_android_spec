from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    ai_provider,
    database_session,
    push_provider,
    readiness_checker,
    redis_client,
)
from app.services.ai_grounding import AIAnalysisProvider
from app.services.production_readiness import ProductionReadinessService
from app.services.push_notifications import PushNotificationProvider
from app.services.readiness import ReadinessChecker

router = APIRouter()


@router.get("/health", operation_id="health_check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", operation_id="readiness_check")
async def ready(
    checker: Annotated[ReadinessChecker, Depends(readiness_checker)],
) -> dict[str, object]:
    checks = await checker.check()
    return {"status": "ready", "checks": checks}


@router.get("/production-readiness", operation_id="production_readiness_check")
async def production_readiness(
    session: Annotated[AsyncSession, Depends(database_session)],
    current_ai_provider: Annotated[AIAnalysisProvider, Depends(ai_provider)],
    current_push_provider: Annotated[PushNotificationProvider, Depends(push_provider)],
    redis: Annotated[Any, Depends(redis_client)] = None,
) -> dict[str, Any]:
    service = ProductionReadinessService(
        session=session,
        ai_provider=current_ai_provider,
        push_provider=current_push_provider,
        redis_client=redis,
    )
    return await service.check_health()
