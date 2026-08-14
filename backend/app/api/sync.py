from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.dependencies import cloud_sync_service, current_user

router = APIRouter(prefix="/sync", tags=["Sync"])


class SyncOperationInput(BaseModel):
    operation_id: UUID
    entity_type: Literal[
        "WATCHLIST",
        "WATCHLIST_ITEM",
        "PORTFOLIO",
        "PORTFOLIO_TRANSACTION",
        "ALERT_RULE",
        "SAVED_SCREENER",
        "USER_SETTING",
    ]
    entity_id: UUID
    operation: Literal["UPSERT", "DELETE"]
    base_version: int = Field(ge=0)
    payload: dict | None = None


class SyncPushInput(BaseModel):
    device_id: UUID
    operations: list[SyncOperationInput] = Field(max_length=100)


@router.post("/push")
async def push(
    payload: SyncPushInput,
    user: Annotated[object, Depends(current_user)],
    service: Annotated[object, Depends(cloud_sync_service)],
):
    return {
        "data": {
            "results": await service.push(
                user.id, payload.device_id, [row.model_dump() for row in payload.operations]
            )
        }
    }


@router.get("/changes")
async def changes(
    user: Annotated[object, Depends(current_user)],
    service: Annotated[object, Depends(cloud_sync_service)],
    cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    return {"data": await service.changes(user.id, cursor, limit)}


@router.get("/bootstrap")
async def bootstrap(
    user: Annotated[object, Depends(current_user)],
    service: Annotated[object, Depends(cloud_sync_service)],
):
    return {"data": await service.bootstrap(user.id)}
