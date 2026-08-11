from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode, SecurityRepository
from app.domain.watchlist import WatchlistRepository


class WatchlistService:
    def __init__(self, repository: WatchlistRepository, securities: SecurityRepository):
        self.repository = repository
        self.securities = securities

    @staticmethod
    def clean_name(name: str) -> str:
        value = name.strip()
        if not value:
            raise AppError("WATCHLIST_INVALID_NAME", "自選群組名稱不可為空", 422)
        return value

    async def require(self, watchlist_id: UUID):
        row = await self.repository.get_watchlist(watchlist_id)
        if row is None:
            raise AppError("WATCHLIST_NOT_FOUND", "找不到自選群組", 404)
        return row

    async def create(self, name: str):
        return await self.repository.create_watchlist(self.clean_name(name))

    async def rename(self, watchlist_id: UUID, name: str):
        await self.require(watchlist_id)
        return await self.repository.rename_watchlist(watchlist_id, self.clean_name(name))

    async def delete(self, watchlist_id: UUID):
        await self.require(watchlist_id)
        await self.repository.delete_watchlist(watchlist_id)

    async def add_security(self, watchlist_id: UUID, code: str, market: MarketCode | None):
        await self.require(watchlist_id)
        matches = await self.securities.find_by_code(code, market)
        if not matches:
            raise AppError("SECURITY_NOT_FOUND", "找不到指定股票", 404)
        if len(matches) > 1:
            raise AppError("AMBIGUOUS_SECURITY", "股票代號存在於多個市場，請指定 market", 409)
        if any(
            item.security_id == matches[0].id
            for item in await self.repository.list_items(watchlist_id)
        ):
            raise AppError("WATCHLIST_ITEM_EXISTS", "此股票已在目前自選群組", 409)
        return await self.repository.add_item(watchlist_id, matches[0].id)

    async def update_item(self, watchlist_id: UUID, item_id: UUID, note, target, stop, add):
        await self.require(watchlist_id)
        for value in (target, stop, add):
            if value is not None and value <= Decimal("0"):
                raise AppError("WATCHLIST_INVALID_PRICE", "價格設定必須大於 0", 422)
        normalized = note.strip() if note else None
        if normalized and len(normalized) > 500:
            raise AppError("WATCHLIST_NOTE_TOO_LONG", "備註不可超過 500 字", 422)
        row = await self.repository.update_item(
            watchlist_id,
            item_id,
            note=normalized or None,
            target_price=target,
            stop_price=stop,
            add_price=add,
        )
        if row is None:
            raise AppError("WATCHLIST_ITEM_NOT_FOUND", "找不到自選股票", 404)
        return row

    async def remove(self, watchlist_id: UUID, item_id: UUID):
        await self.require(watchlist_id)
        if not await self.repository.delete_item(watchlist_id, item_id):
            raise AppError("WATCHLIST_ITEM_NOT_FOUND", "找不到自選股票", 404)

    async def reorder_groups(self, orders):
        if len({item[0] for item in orders}) != len(
            orders
        ) or not await self.repository.reorder_watchlists(orders):
            raise AppError("WATCHLIST_INVALID_REORDER", "群組排序資料無效", 422)

    async def reorder_items(self, watchlist_id, orders):
        await self.require(watchlist_id)
        if len({item[0] for item in orders}) != len(
            orders
        ) or not await self.repository.reorder_items(watchlist_id, orders):
            raise AppError("WATCHLIST_INVALID_REORDER", "股票排序資料無效", 422)

    async def overview(self, watchlist_id):
        await self.require(watchlist_id)
        rows = await self.repository.overview(watchlist_id)
        for row in rows:
            statuses = [
                row.get("price_status"),
                row.get("technical_status"),
                row.get("credit_status"),
            ]
            if row.get("close") is None:
                row["data_status"] = DataStatus.UNAVAILABLE
            elif any(value in (None, DataStatus.UNAVAILABLE) for value in statuses):
                row["data_status"] = DataStatus.PARTIAL
            elif any(value == DataStatus.STALE for value in statuses):
                row["data_status"] = DataStatus.STALE
            else:
                row["data_status"] = DataStatus.FINAL
            row["price_above_ma20"] = (
                row.get("close") > row.get("ma20")
                if row.get("close") is not None and row.get("ma20") is not None
                else None
            )
            row["price_above_ma60"] = (
                row.get("close") > row.get("ma60")
                if row.get("close") is not None and row.get("ma60") is not None
                else None
            )
        return rows
