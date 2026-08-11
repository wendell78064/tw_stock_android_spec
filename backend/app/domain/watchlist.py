from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.domain.security import MarketCode


@dataclass(frozen=True)
class Watchlist:
    id: UUID
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WatchlistItem:
    id: UUID
    watchlist_id: UUID
    security_id: UUID
    security_code: str
    security_name: str
    market: MarketCode
    sort_order: int
    note: str | None
    target_price: Decimal | None
    stop_price: Decimal | None
    add_price: Decimal | None
    created_at: datetime
    updated_at: datetime


class WatchlistRepository(Protocol):
    async def list_watchlists(self) -> list[Watchlist]: ...
    async def get_watchlist(self, watchlist_id: UUID) -> Watchlist | None: ...
    async def create_watchlist(self, name: str) -> Watchlist: ...
    async def rename_watchlist(self, watchlist_id: UUID, name: str) -> Watchlist | None: ...
    async def delete_watchlist(self, watchlist_id: UUID) -> bool: ...
    async def reorder_watchlists(self, orders: list[tuple[UUID, int]]) -> bool: ...
    async def list_items(self, watchlist_id: UUID) -> list[WatchlistItem]: ...
    async def get_item(self, watchlist_id: UUID, item_id: UUID) -> WatchlistItem | None: ...
    async def add_item(self, watchlist_id: UUID, security_id: UUID) -> WatchlistItem: ...
    async def update_item(
        self, watchlist_id: UUID, item_id: UUID, **values
    ) -> WatchlistItem | None: ...
    async def delete_item(self, watchlist_id: UUID, item_id: UUID) -> bool: ...
    async def reorder_items(self, watchlist_id: UUID, orders: list[tuple[UUID, int]]) -> bool: ...
    async def overview(self, watchlist_id: UUID) -> list[dict]: ...
