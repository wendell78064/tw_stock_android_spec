from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.security import MarketCode
from app.domain.watchlist import Watchlist, WatchlistItem
from app.repositories.models import MarketModel, SecurityModel, WatchlistItemModel, WatchlistModel


class SqlWatchlistRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_watchlists(self):
        rows = (
            await self.session.scalars(
                select(WatchlistModel)
                .where(WatchlistModel.user_id.is_(None), WatchlistModel.deleted_at.is_(None))
                .order_by(WatchlistModel.sort_order, WatchlistModel.id)
            )
        ).all()
        return [self._watchlist(row) for row in rows]

    async def get_watchlist(self, watchlist_id):
        row = await self.session.get(WatchlistModel, watchlist_id)
        return (
            self._watchlist(row) if row and row.user_id is None and row.deleted_at is None else None
        )

    async def create_watchlist(self, name):
        order = await self.session.scalar(
            select(func.coalesce(func.max(WatchlistModel.sort_order), -1)).where(
                WatchlistModel.user_id.is_(None), WatchlistModel.deleted_at.is_(None)
            )
        )
        now = datetime.now(UTC)
        row = WatchlistModel(name=name, sort_order=order + 1, created_at=now, updated_at=now)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._watchlist(row)

    async def rename_watchlist(self, watchlist_id, name):
        row = await self.session.get(WatchlistModel, watchlist_id)
        if not row or row.user_id is not None or row.deleted_at is not None:
            return None
        row.name, row.updated_at = name, datetime.now(UTC)
        await self.session.commit()
        return self._watchlist(row)

    async def delete_watchlist(self, watchlist_id):
        result = await self.session.execute(
            delete(WatchlistModel).where(
                WatchlistModel.id == watchlist_id, WatchlistModel.user_id.is_(None)
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def reorder_watchlists(self, orders):
        ids = [item[0] for item in orders]
        existing = set(
            (
                await self.session.scalars(
                    select(WatchlistModel.id).where(
                        WatchlistModel.id.in_(ids), WatchlistModel.user_id.is_(None)
                    )
                )
            ).all()
        )
        if len(existing) != len(ids):
            return False
        now = datetime.now(UTC)
        for item_id, sort_order in orders:
            await self.session.execute(
                update(WatchlistModel)
                .where(WatchlistModel.id == item_id)
                .values(sort_order=sort_order, updated_at=now)
            )
        await self.session.commit()
        return True

    async def list_items(self, watchlist_id):
        statement = (
            select(WatchlistItemModel, SecurityModel, MarketModel.code)
            .join(SecurityModel, SecurityModel.id == WatchlistItemModel.security_id)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(WatchlistItemModel.watchlist_id == watchlist_id)
            .where(WatchlistItemModel.user_id.is_(None), WatchlistItemModel.deleted_at.is_(None))
            .order_by(WatchlistItemModel.sort_order, WatchlistItemModel.id)
        )
        return [self._item(*row) for row in (await self.session.execute(statement)).all()]

    async def get_item(self, watchlist_id, item_id):
        statement = (
            select(WatchlistItemModel, SecurityModel, MarketModel.code)
            .join(SecurityModel, SecurityModel.id == WatchlistItemModel.security_id)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(
                WatchlistItemModel.watchlist_id == watchlist_id,
                WatchlistItemModel.id == item_id,
                WatchlistItemModel.user_id.is_(None),
                WatchlistItemModel.deleted_at.is_(None),
            )
        )
        row = (await self.session.execute(statement)).one_or_none()
        return self._item(*row) if row else None

    async def add_item(self, watchlist_id, security_id):
        order = await self.session.scalar(
            select(func.coalesce(func.max(WatchlistItemModel.sort_order), -1)).where(
                WatchlistItemModel.watchlist_id == watchlist_id
            )
        )
        now = datetime.now(UTC)
        row = WatchlistItemModel(
            watchlist_id=watchlist_id,
            security_id=security_id,
            sort_order=order + 1,
            created_at=now,
            updated_at=now,
        )
        self.session.add(row)
        await self.session.commit()
        return await self.get_item(watchlist_id, row.id)

    async def update_item(self, watchlist_id, item_id, **values):
        row = await self.session.get(WatchlistItemModel, item_id)
        if not row or row.watchlist_id != watchlist_id or row.user_id is not None:
            return None
        for key, value in values.items():
            setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        await self.session.commit()
        return await self.get_item(watchlist_id, item_id)

    async def delete_item(self, watchlist_id, item_id):
        result = await self.session.execute(
            delete(WatchlistItemModel).where(
                WatchlistItemModel.watchlist_id == watchlist_id,
                WatchlistItemModel.id == item_id,
                WatchlistItemModel.user_id.is_(None),
            )
        )
        await self.session.commit()
        return bool(result.rowcount)

    async def reorder_items(self, watchlist_id, orders):
        ids = [item[0] for item in orders]
        existing = set(
            (
                await self.session.scalars(
                    select(WatchlistItemModel.id).where(
                        WatchlistItemModel.watchlist_id == watchlist_id,
                        WatchlistItemModel.id.in_(ids),
                        WatchlistItemModel.user_id.is_(None),
                    )
                )
            ).all()
        )
        if len(existing) != len(ids):
            return False
        now = datetime.now(UTC)
        for item_id, sort_order in orders:
            await self.session.execute(
                update(WatchlistItemModel)
                .where(WatchlistItemModel.id == item_id)
                .values(sort_order=sort_order, updated_at=now)
            )
        await self.session.commit()
        return True

    async def overview(self, watchlist_id):
        query = text("""
        WITH item_security AS (
          SELECT wi.*, s.code, s.name security_name, m.code market
          FROM watchlist_items wi
          JOIN securities s ON s.id=wi.security_id
          JOIN markets m ON m.id=s.market_id
          WHERE wi.watchlist_id=:watchlist_id AND wi.user_id IS NULL AND wi.deleted_at IS NULL
        ), prices AS (
          SELECT DISTINCT ON (security_id) security_id, trade_date, close, data_status,
            close - lag_close AS change,
            CASE WHEN lag_close <> 0 THEN (close-lag_close)/lag_close*100 END change_percent
          FROM (SELECT security_id, trade_date, close, data_status,
            lag(close) OVER (PARTITION BY security_id ORDER BY trade_date) lag_close
            FROM daily_prices WHERE security_id IN (SELECT security_id FROM item_security)) p
          ORDER BY security_id, trade_date DESC
        ), technicals AS (
          SELECT DISTINCT ON (security_id)
            security_id,trade_date,ma5,ma20,ma60,rsi14,data_status
          FROM technical_snapshots
          WHERE security_id IN (SELECT security_id FROM item_security)
            AND price_basis='RAW'
          ORDER BY security_id, trade_date DESC
        ), institutions AS (
          SELECT security_id, trade_date,
            max(net_shares) FILTER (WHERE institution_type='FOREIGN') foreign_net,
            max(net_shares) FILTER (WHERE institution_type='INVESTMENT_TRUST') investment_trust_net,
            sum(net_shares) FILTER (WHERE institution_type='DEALER') dealer_net
          FROM institution_spot_trading
          WHERE (security_id,trade_date) IN (
            SELECT security_id,max(trade_date) FROM institution_spot_trading
            WHERE security_id IN (SELECT security_id FROM item_security)
            GROUP BY security_id
          )
          GROUP BY security_id,trade_date
        ), credits AS (
          SELECT DISTINCT ON (security_id) security_id,trade_date,
            margin_balance,margin_balance_change,short_balance,short_balance_change,data_status
          FROM margin_trading WHERE security_id IN (SELECT security_id FROM item_security)
          ORDER BY security_id, trade_date DESC
        )
        SELECT i.*,p.trade_date price_as_of,p.close,p.change,p.change_percent,
          p.data_status price_status,
          t.ma5,t.ma20,t.ma60,t.rsi14,t.data_status technical_status,
          n.foreign_net,n.investment_trust_net,n.dealer_net,
          c.margin_balance,c.margin_balance_change,c.short_balance,c.short_balance_change,
          c.data_status credit_status
        FROM item_security i LEFT JOIN prices p USING(security_id)
        LEFT JOIN technicals t USING(security_id)
        LEFT JOIN institutions n USING(security_id) LEFT JOIN credits c USING(security_id)
        ORDER BY i.sort_order,i.id
        """)
        return [
            dict(row._mapping)
            for row in (await self.session.execute(query, {"watchlist_id": watchlist_id})).all()
        ]

    @staticmethod
    def _watchlist(row):
        return Watchlist(row.id, row.name, row.sort_order, row.created_at, row.updated_at)

    @staticmethod
    def _item(row, security, market):
        return WatchlistItem(
            row.id,
            row.watchlist_id,
            row.security_id,
            security.code,
            security.name,
            MarketCode(market),
            row.sort_order,
            row.note,
            Decimal(row.target_price) if row.target_price is not None else None,
            Decimal(row.stop_price) if row.stop_price is not None else None,
            Decimal(row.add_price) if row.add_price is not None else None,
            row.created_at,
            row.updated_at,
        )
