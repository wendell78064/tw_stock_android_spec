from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import current_user, database_session, push_provider, redis_client
from app.services.push_notifications import PushNotificationProvider, PushNotificationService

router = APIRouter(prefix="/push", tags=["push"])


class RegisterPushTokenRequest(BaseModel):
    device_public_id: str = Field(..., min_length=1, max_length=128)
    push_token: str = Field(..., min_length=1, max_length=512)
    platform: str = Field(default="ANDROID", max_length=32)


class PushTokenActionResponse(BaseModel):
    status: str = "SUCCESS"


class UnregisterPushTokenRequest(BaseModel):
    device_public_id: str = Field(..., min_length=1, max_length=128)


@router.post("/register", response_model=PushTokenActionResponse)
async def register_push_token(
    req: RegisterPushTokenRequest,
    session: Annotated[AsyncSession, Depends(database_session)],
    user: Annotated[Any, Depends(current_user)],
    provider: Annotated[PushNotificationProvider, Depends(push_provider)],
    redis: Annotated[Any, Depends(redis_client)] = None,
) -> PushTokenActionResponse:
    service = PushNotificationService(session, provider, redis)
    await service.register_token(
        user_id=user.id,
        device_public_id=req.device_public_id,
        token=req.push_token,
        platform=req.platform,
    )
    return PushTokenActionResponse(status="REGISTERED")


@router.post("/unregister", response_model=PushTokenActionResponse)
async def unregister_push_token(
    req: UnregisterPushTokenRequest,
    session: Annotated[AsyncSession, Depends(database_session)],
    user: Annotated[Any, Depends(current_user)],
    provider: Annotated[PushNotificationProvider, Depends(push_provider)],
    redis: Annotated[Any, Depends(redis_client)] = None,
) -> PushTokenActionResponse:
    service = PushNotificationService(session, provider, redis)
    await service.unregister_token(
        user_id=user.id,
        device_public_id=req.device_public_id,
    )
    return PushTokenActionResponse(status="UNREGISTERED")
