from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.dependencies import auth_service, current_user

router = APIRouter(tags=["Auth"])


class Credentials(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class RefreshInput(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)


class DeviceInput(BaseModel):
    device_public_id: str = Field(min_length=16, max_length=128)
    name: str | None = Field(default=None, max_length=120)
    platform: str = Field(default="ANDROID", max_length=24)
    app_version: str | None = Field(default=None, max_length=32)


def account(user):
    return {"id": str(user.id), "identifier": user.login_identifier, "status": user.status}


@router.post("/auth/register", status_code=201)
async def register(payload: Credentials, service: Annotated[object, Depends(auth_service)]):
    return {"data": account(await service.register(payload.identifier, payload.password))}


@router.post("/auth/login")
async def login(payload: Credentials, service: Annotated[object, Depends(auth_service)]):
    return {"data": await service.login(payload.identifier, payload.password)}


@router.post("/auth/refresh")
async def refresh(payload: RefreshInput, service: Annotated[object, Depends(auth_service)]):
    return {"data": await service.refresh(payload.refresh_token)}


@router.post("/auth/logout", status_code=204)
async def logout(payload: RefreshInput, service: Annotated[object, Depends(auth_service)]):
    await service.logout(payload.refresh_token)


@router.get("/me")
async def me(user: Annotated[object, Depends(current_user)]):
    return {"data": account(user)}


@router.post("/devices")
async def register_device(
    payload: DeviceInput,
    user: Annotated[object, Depends(current_user)],
    service: Annotated[object, Depends(auth_service)],
):
    row = await service.upsert_device(
        user.id, payload.device_public_id, payload.name, payload.platform, payload.app_version
    )
    return {"data": {"id": str(row.id), "device_public_id": row.device_public_id}}
