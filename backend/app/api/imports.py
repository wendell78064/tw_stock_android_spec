from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.core.dependencies import current_user, database_session, get_redis_client
from app.repositories.models import UserModel
from app.services.import_export import ImportService

router = APIRouter(prefix="/imports", tags=["Imports"])


class PortfolioApplyInput(BaseModel):
    preview_token: str = Field(
        ..., description="Preview token returned from /imports/portfolio/preview"
    )
    portfolio_id: UUID = Field(..., description="Target portfolio UUID")


class WatchlistApplyInput(BaseModel):
    preview_token: str = Field(
        ..., description="Preview token returned from /imports/watchlists/preview"
    )
    merge_mode: str = Field("MERGE", description="MERGE or REPLACE")


class CsvTextInput(BaseModel):
    csv_content: str = Field(..., description="CSV raw text content")
    portfolio_id: UUID | None = None
    merge_mode: str = "MERGE"


@router.post("/portfolio/preview")
async def preview_portfolio_import(
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
    redis_client: Annotated[object, Depends(get_redis_client)],
    file: UploadFile | None = File(None),
    body: CsvTextInput | None = Body(None),
    portfolio_id: UUID | None = Form(None),
):
    service = ImportService(session, redis_client)
    target_pid = portfolio_id
    if file:
        content_bytes = await file.read()
        csv_text = content_bytes.decode("utf-8-sig", errors="replace")
    elif body and body.csv_content:
        csv_text = body.csv_content
        target_pid = body.portfolio_id or target_pid
    else:
        csv_text = ""

    result = await service.preview_portfolio_csv(user.id, csv_text, target_pid)
    return {"data": result}


@router.post("/portfolio/apply")
async def apply_portfolio_import(
    input_data: PortfolioApplyInput,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
    redis_client: Annotated[object, Depends(get_redis_client)],
):
    service = ImportService(session, redis_client)
    result = await service.apply_portfolio_import(
        user.id, input_data.preview_token, input_data.portfolio_id
    )
    return {"data": result}


@router.post("/watchlists/preview")
async def preview_watchlist_import(
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
    redis_client: Annotated[object, Depends(get_redis_client)],
    file: UploadFile | None = File(None),
    body: CsvTextInput | None = Body(None),
    merge_mode: str = Form("MERGE"),
):
    service = ImportService(session, redis_client)
    mode = merge_mode
    if file:
        content_bytes = await file.read()
        csv_text = content_bytes.decode("utf-8-sig", errors="replace")
    elif body and body.csv_content:
        csv_text = body.csv_content
        mode = body.merge_mode or mode
    else:
        csv_text = ""

    result = await service.preview_watchlist_csv(user.id, csv_text, mode)
    return {"data": result}


@router.post("/watchlists/apply")
async def apply_watchlist_import(
    input_data: WatchlistApplyInput,
    user: Annotated[UserModel, Depends(current_user)],
    session: Annotated[object, Depends(database_session)],
    redis_client: Annotated[object, Depends(get_redis_client)],
):
    service = ImportService(session, redis_client)
    result = await service.apply_watchlist_import(
        user.id, input_data.preview_token, input_data.merge_mode
    )
    return {"data": result}
