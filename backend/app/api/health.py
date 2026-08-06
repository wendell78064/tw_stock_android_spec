from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import readiness_checker
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
