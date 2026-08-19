from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_data import DataStatus
from app.domain.pricing import DailyPriceRecord, PriceBasis, SecurityKey, TechnicalSnapshot
from app.repositories.models import (
    DailyPriceModel,
    MarketModel,
    SecurityModel,
    TechnicalSnapshotModel,
)

INDICATOR_COLUMNS = {
    "MA5": "ma5",
    "MA10": "ma10",
    "MA20": "ma20",
    "MA60": "ma60",
    "MA120": "ma120",
    "MA240": "ma240",
    "EMA12": "ema12",
    "EMA26": "ema26",
    "RSI14": "rsi14",
    "MACD": "macd",
    "MACD_SIGNAL": "macd_signal",
    "MACD_HISTOGRAM": "macd_histogram",
    "KD_K": "kd_k",
    "KD_D": "kd_d",
    "ATR14": "atr14",
    "OBV": "obv",
    "BBANDS_UPPER": "bollinger_upper",
    "BBANDS_MIDDLE": "bollinger_middle",
    "BBANDS_LOWER": "bollinger_lower",
    "WILLIAMS_R": "williams_r",
}


class SqlPriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _preload_security_ids(
        self, keys: set[SecurityKey] | None = None
    ) -> dict[SecurityKey, UUID]:
        stmt = (
            select(MarketModel.code, SecurityModel.code, SecurityModel.id)
            .join(MarketModel)
            .where(
                SecurityModel.is_active.is_(True),
                SecurityModel.security_type == SecurityType.COMMON_STOCK,
            )
        )
        if keys is not None:
            market_codes = {k.market.value for k in keys}
            codes = {k.code for k in keys}
            stmt = stmt.where(MarketModel.code.in_(market_codes), SecurityModel.code.in_(codes))
        rows = (await self.session.execute(stmt)).all()
        return {SecurityKey(MarketCode(m), c): sid for m, c, sid in rows}

    async def _security_id(self, key: SecurityKey) -> UUID | None:
        mapping = await self._preload_security_ids({key})
        return mapping.get(key)

    async def synchronize(self, records: list[DailyPriceRecord], run_id: UUID) -> tuple[int, int]:
        if not records:
            return 0, 0
        inserted = updated = 0
        seen: set[tuple[SecurityKey, date]] = set()
        keys = {r.security for r in records}
        security_id_map = await self._preload_security_ids(keys)

        sec_ids = list(set(security_id_map.values()))
        dates = list({r.trade_date for r in records})
        existing_models = {}
        if sec_ids and dates:
            existing_stmt = select(DailyPriceModel).where(
                DailyPriceModel.security_id.in_(sec_ids),
                DailyPriceModel.trade_date.in_(dates),
            )
            for m in (await self.session.scalars(existing_stmt)).all():
                existing_models[(m.security_id, m.trade_date)] = m

        for record in records:
            identity = (record.security, record.trade_date)
            if identity in seen:
                raise ValueError(f"duplicate daily price: {record.security}:{record.trade_date}")
            seen.add(identity)
            security_id = security_id_map.get(record.security)
            if security_id is None:
                raise LookupError(
                    f"missing security: {record.security.market}:{record.security.code}"
                )
            model = existing_models.get((security_id, record.trade_date))
            values = self._record_values(record, run_id)
            if model is None:
                new_model = DailyPriceModel(security_id=security_id, **values)
                self.session.add(new_model)
                existing_models[(security_id, record.trade_date)] = new_model
                inserted += 1
            elif any(
                getattr(model, key) != value
                for key, value in values.items()
                if key != "ingestion_run_id"
            ):
                for key, value in values.items():
                    setattr(model, key, value)
                updated += 1
        await self.session.flush()
        return inserted, updated

    @staticmethod
    def _record_values(record: DailyPriceRecord, run_id: UUID) -> dict:
        return {
            "trade_date": record.trade_date,
            "open": record.open,
            "high": record.high,
            "low": record.low,
            "close": record.close,
            "adjusted_open": record.adjusted_open,
            "adjusted_high": record.adjusted_high,
            "adjusted_low": record.adjusted_low,
            "adjusted_close": record.adjusted_close,
            "volume_shares": record.volume_shares,
            "turnover_amount": record.turnover_amount,
            "source_code": record.source_code,
            "as_of": record.as_of,
            "received_at": record.received_at,
            "data_status": record.data_status,
            "source_revision": record.source_revision,
            "missing_reason": record.missing_reason,
            "ingestion_run_id": run_id,
        }

    async def list_prices(
        self, security: SecurityKey, start_date: date | None, end_date: date | None
    ) -> list[DailyPriceRecord]:
        security_id = await self._security_id(security)
        if security_id is None:
            return []
        statement = select(DailyPriceModel).where(DailyPriceModel.security_id == security_id)
        if start_date:
            statement = statement.where(DailyPriceModel.trade_date >= start_date)
        if end_date:
            statement = statement.where(DailyPriceModel.trade_date <= end_date)
        models = (await self.session.scalars(statement.order_by(DailyPriceModel.trade_date))).all()
        return [
            DailyPriceRecord(
                security,
                item.trade_date,
                item.open,
                item.high,
                item.low,
                item.close,
                item.adjusted_open,
                item.adjusted_high,
                item.adjusted_low,
                item.adjusted_close,
                item.volume_shares,
                item.turnover_amount,
                item.source_code,
                item.as_of,
                item.received_at,
                DataStatus(item.data_status),
                item.source_revision,
                item.missing_reason,
            )
            for item in models
        ]

    async def replace_technicals(
        self, security: SecurityKey, basis: PriceBasis, snapshots: list[TechnicalSnapshot]
    ) -> None:
        security_id = await self._security_id(security)
        if security_id is None:
            raise LookupError(f"missing security: {security}")
        await self.session.execute(
            delete(TechnicalSnapshotModel).where(
                TechnicalSnapshotModel.security_id == security_id,
                TechnicalSnapshotModel.price_basis == basis.value,
            )
        )
        for snapshot in snapshots:
            fields = {
                column: snapshot.values.get(name) for name, column in INDICATOR_COLUMNS.items()
            }
            self.session.add(
                TechnicalSnapshotModel(
                    security_id=security_id,
                    trade_date=snapshot.trade_date,
                    price_basis=basis.value,
                    algorithm_version=snapshot.algorithm_version,
                    as_of=snapshot.as_of,
                    received_at=snapshot.received_at,
                    data_status=snapshot.data_status,
                    **fields,
                )
            )
        await self.session.flush()

    async def list_technicals(
        self,
        security: SecurityKey,
        basis: PriceBasis,
        start_date: date | None,
        end_date: date | None,
    ) -> list[TechnicalSnapshot]:
        security_id = await self._security_id(security)
        if security_id is None:
            return []
        statement = select(TechnicalSnapshotModel).where(
            TechnicalSnapshotModel.security_id == security_id,
            TechnicalSnapshotModel.price_basis == basis.value,
        )
        if start_date:
            statement = statement.where(TechnicalSnapshotModel.trade_date >= start_date)
        if end_date:
            statement = statement.where(TechnicalSnapshotModel.trade_date <= end_date)
        models = (
            await self.session.scalars(
                statement.order_by(TechnicalSnapshotModel.trade_date.desc()).limit(1500)
            )
        ).all()
        return list(
            reversed(
                [
                    TechnicalSnapshot(
                        security,
                        item.trade_date,
                        basis,
                        {name: getattr(item, column) for name, column in INDICATOR_COLUMNS.items()},
                        item.algorithm_version,
                        item.as_of,
                        item.received_at,
                        DataStatus(item.data_status),
                    )
                    for item in models
                ]
            )
        )
