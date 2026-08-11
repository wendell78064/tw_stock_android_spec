from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from app.core.dependencies import security_repository, watchlist_repository
from app.domain.security import MarketCode, SecurityRepository
from app.domain.watchlist import WatchlistRepository
from app.services.watchlist import WatchlistService

router = APIRouter(prefix="/watchlists", tags=["Watchlists"])


class NameInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class AddItemInput(BaseModel):
    security_code: str = Field(min_length=1, max_length=16)
    market: MarketCode | None = None


class ItemInput(BaseModel):
    note: str | None = Field(default=None, max_length=500)
    target_price: Decimal | None = Field(default=None, gt=0)
    stop_price: Decimal | None = Field(default=None, gt=0)
    add_price: Decimal | None = Field(default=None, gt=0)


class OrderInput(BaseModel):
    id: UUID
    sort_order: int = Field(ge=0)


def service(repository, securities):
    return WatchlistService(repository, securities)


def decimal(value):
    return format(value, "f") if value is not None else None


def group(row):
    return {
        "id": str(row.id),
        "name": row.name,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def item(row):
    return {
        "id": str(row.id),
        "watchlist_id": str(row.watchlist_id),
        "security_code": row.security_code,
        "security_name": row.security_name,
        "market": row.market.value,
        "sort_order": row.sort_order,
        "note": row.note,
        "target_price": decimal(row.target_price),
        "stop_price": decimal(row.stop_price),
        "add_price": decimal(row.add_price),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def overview(row):
    result = {
        key: value
        for key, value in row.items()
        if key
        not in {
            "security_id",
            "price_status",
            "technical_status",
            "credit_status",
            "created_at",
            "updated_at",
        }
    }
    for key in ("id", "watchlist_id"):
        result[key] = str(result[key])
    for key in (
        "target_price",
        "stop_price",
        "add_price",
        "close",
        "change",
        "change_percent",
        "ma5",
        "ma20",
        "ma60",
        "rsi14",
    ):
        result[key] = decimal(result.get(key))
    result["price_as_of"] = result["price_as_of"].isoformat() if result.get("price_as_of") else None
    result["data_status"] = result["data_status"].value
    return result


Repo = Annotated[WatchlistRepository, Depends(watchlist_repository)]
Securities = Annotated[SecurityRepository, Depends(security_repository)]


@router.get("", operation_id="listWatchlists")
async def list_watchlists(repository: Repo):
    return {"data": [group(row) for row in await repository.list_watchlists()]}


@router.post("", status_code=201, operation_id="createWatchlist")
async def create_watchlist(payload: NameInput, repository: Repo, securities: Securities):
    return {"data": group(await service(repository, securities).create(payload.name))}


@router.get("/{watchlist_id}", operation_id="getWatchlist")
async def get_watchlist(watchlist_id: UUID, repository: Repo, securities: Securities):
    return {"data": group(await service(repository, securities).require(watchlist_id))}


@router.patch("/{watchlist_id}", operation_id="renameWatchlist")
async def rename_watchlist(
    watchlist_id: UUID, payload: NameInput, repository: Repo, securities: Securities
):
    return {"data": group(await service(repository, securities).rename(watchlist_id, payload.name))}


@router.delete("/{watchlist_id}", status_code=204, operation_id="deleteWatchlist")
async def delete_watchlist(watchlist_id: UUID, repository: Repo, securities: Securities):
    await service(repository, securities).delete(watchlist_id)
    return Response(status_code=204)


@router.put("/reorder", operation_id="reorderWatchlists")
async def reorder_watchlists(payload: list[OrderInput], repository: Repo, securities: Securities):
    await service(repository, securities).reorder_groups(
        [(row.id, row.sort_order) for row in payload]
    )
    return {"data": [group(row) for row in await repository.list_watchlists()]}


@router.get("/{watchlist_id}/items", operation_id="listWatchlistItems")
async def list_items(watchlist_id: UUID, repository: Repo, securities: Securities):
    await service(repository, securities).require(watchlist_id)
    return {"data": [item(row) for row in await repository.list_items(watchlist_id)]}


@router.post("/{watchlist_id}/items", status_code=201, operation_id="addWatchlistItem")
async def add_item(
    watchlist_id: UUID, payload: AddItemInput, repository: Repo, securities: Securities
):
    return {
        "data": item(
            await service(repository, securities).add_security(
                watchlist_id, payload.security_code, payload.market
            )
        )
    }


@router.patch("/{watchlist_id}/items/{item_id}", operation_id="updateWatchlistItem")
async def update_item(
    watchlist_id: UUID, item_id: UUID, payload: ItemInput, repository: Repo, securities: Securities
):
    return {
        "data": item(
            await service(repository, securities).update_item(
                watchlist_id,
                item_id,
                payload.note,
                payload.target_price,
                payload.stop_price,
                payload.add_price,
            )
        )
    }


@router.delete(
    "/{watchlist_id}/items/{item_id}", status_code=204, operation_id="deleteWatchlistItem"
)
async def delete_item(watchlist_id: UUID, item_id: UUID, repository: Repo, securities: Securities):
    await service(repository, securities).remove(watchlist_id, item_id)
    return Response(status_code=204)


@router.put("/{watchlist_id}/items/reorder", operation_id="reorderWatchlistItems")
async def reorder_items(
    watchlist_id: UUID, payload: list[OrderInput], repository: Repo, securities: Securities
):
    await service(repository, securities).reorder_items(
        watchlist_id, [(row.id, row.sort_order) for row in payload]
    )
    return {"data": [item(row) for row in await repository.list_items(watchlist_id)]}


@router.get("/{watchlist_id}/overview", operation_id="getWatchlistOverview")
async def get_overview(watchlist_id: UUID, repository: Repo, securities: Securities):
    return {
        "data": [
            overview(row) for row in await service(repository, securities).overview(watchlist_id)
        ]
    }
