from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import current_user, database_session, redis_client
from app.domain.ai import AnalysisType, StructuredAIAnalysisResult
from app.services.ai_grounding import (
    AIAnalysisService,
    FakeAIProvider,
    UnconfiguredAIProvider,
)

router = APIRouter(prefix="/ai", tags=["ai"])

# In production without real API keys, UnconfiguredAIProvider is default.
# For DEV/TEST environments, FakeAIProvider can be used.
_default_ai_provider = FakeAIProvider()


class AnalyzeRequest(BaseModel):
    analysis_type: AnalysisType
    target_id: UUID | None = None
    comparison_ids: list[UUID] | None = None
    screener_expression: dict[str, Any] | None = None


class AIConsentResponse(BaseModel):
    allow_portfolio_analysis: bool


class SetAIConsentRequest(BaseModel):
    allow_portfolio_analysis: bool


@router.post("/analyze", response_model=StructuredAIAnalysisResult)
async def run_ai_analysis(
    req: AnalyzeRequest,
    session: Annotated[AsyncSession, Depends(database_session)],
    user: Annotated[Any, Depends(current_user)],
    redis: Annotated[Any, Depends(redis_client)] = None,
) -> StructuredAIAnalysisResult:
    user_id = user.id if user else None
    service = AIAnalysisService(session, _default_ai_provider, redis)
    return await service.analyze(
        analysis_type=req.analysis_type,
        user_id=user_id,
        target_id=req.target_id,
        comparison_ids=req.comparison_ids,
        screener_expression=req.screener_expression,
    )


@router.get("/consent", response_model=AIConsentResponse)
async def get_ai_consent(
    session: Annotated[AsyncSession, Depends(database_session)],
    user: Annotated[Any, Depends(current_user)],
) -> AIConsentResponse:
    service = AIAnalysisService(session, _default_ai_provider)
    allowed = await service.check_portfolio_consent(user.id)
    return AIConsentResponse(allow_portfolio_analysis=allowed)


@router.post("/consent", response_model=AIConsentResponse)
async def set_ai_consent(
    req: SetAIConsentRequest,
    session: Annotated[AsyncSession, Depends(database_session)],
    user: Annotated[Any, Depends(current_user)],
) -> AIConsentResponse:
    service = AIAnalysisService(session, _default_ai_provider)
    await service.set_portfolio_consent(user.id, req.allow_portfolio_analysis)
    return AIConsentResponse(allow_portfolio_analysis=req.allow_portfolio_analysis)
