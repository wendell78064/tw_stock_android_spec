from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.derivatives import (
    ContractStatus,
    FuturesContract,
    FuturesDailyPrice,
    FuturesProduct,
    InstitutionFuturesPosition,
    OptionPutCallRatio,
    OptionStrikeOpenInterest,
    OptionType,
    PositionSide,
    SessionType,
    TraderConcentration,
    VolatilityIndex,
)
from app.domain.market_data import DataStatus
from app.domain.market_spot import InstitutionType, SourceMetadata
from app.repositories.models import (
    FuturesContractModel,
    FuturesDailyPriceModel,
    FuturesProductModel,
    InstitutionFuturesPositionModel,
    OptionPutCallRatioModel,
    OptionStrikeOpenInterestModel,
    TraderConcentrationModel,
    VolatilityIndexModel,
)


class SqlDerivativesRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _product(self, code: str):
        return await self.session.scalar(
            select(FuturesProductModel).where(FuturesProductModel.code == code)
        )

    async def _contract(self, code: str):
        return await self.session.scalar(
            select(FuturesContractModel).where(FuturesContractModel.contract_code == code)
        )

    @staticmethod
    def _meta(row, run_id):
        m = row.metadata
        return {
            "source_code": m.source_code,
            "as_of": m.as_of,
            "received_at": m.received_at,
            "data_status": m.data_status,
            "source_revision": m.source_revision,
            "ingestion_run_id": run_id,
        }

    async def _upsert(self, model_type, where, values):
        model = await self.session.scalar(select(model_type).where(*where))
        if model is None:
            self.session.add(model_type(**values))
            return 1, 0
        compare = {k: v for k, v in values.items() if k != "ingestion_run_id"}
        if any(getattr(model, k) != v for k, v in compare.items()):
            for key, value in values.items():
                setattr(model, key, value)
            return 0, 1
        return 0, 0

    async def synchronize(self, dataset: str, records: list[object], run_id: UUID):
        inserted = updated = 0
        for row in records:
            if isinstance(row, FuturesProduct):
                values = {
                    "code": row.code,
                    "name": row.name,
                    "contract_multiplier": row.contract_multiplier,
                    "currency": row.currency,
                    "session_type": row.session_type.value,
                    "is_active": row.is_active,
                }
                model, where = FuturesProductModel, (FuturesProductModel.code == row.code,)
            elif isinstance(row, FuturesContract):
                product = await self._product(row.product_code)
                if not product:
                    raise LookupError(f"missing product {row.product_code}")
                values = {
                    "product_id": product.id,
                    "contract_code": row.contract_code,
                    "contract_month": row.contract_month,
                    "expiry_date": row.expiry_date,
                    "last_trade_date": row.last_trade_date,
                    "status": row.status.value,
                    "is_active": row.is_active,
                }
                model, where = (
                    FuturesContractModel,
                    (
                        FuturesContractModel.product_id == product.id,
                        FuturesContractModel.contract_code == row.contract_code,
                    ),
                )
            elif isinstance(row, FuturesDailyPrice):
                contract = await self._contract(row.contract_code)
                if not contract:
                    raise LookupError(f"missing contract {row.contract_code}")
                values = {
                    name: getattr(row, name)
                    for name in (
                        "trade_date",
                        "open",
                        "high",
                        "low",
                        "close",
                        "settlement_price",
                        "change",
                        "change_percent",
                        "volume",
                        "open_interest",
                    )
                }
                values.update(
                    {
                        "contract_id": contract.id,
                        "session_type": row.session_type.value,
                        **self._meta(row, run_id),
                    }
                )
                model, where = (
                    FuturesDailyPriceModel,
                    (
                        FuturesDailyPriceModel.contract_id == contract.id,
                        FuturesDailyPriceModel.trade_date == row.trade_date,
                        FuturesDailyPriceModel.session_type == row.session_type.value,
                    ),
                )
            elif isinstance(row, InstitutionFuturesPosition):
                product = await self._product(row.product_code)
                if not product:
                    raise LookupError(f"missing product {row.product_code}")
                values = {
                    name: getattr(row, name)
                    for name in (
                        "trade_date",
                        "long_volume",
                        "short_volume",
                        "net_volume",
                        "long_amount",
                        "short_amount",
                        "net_amount",
                        "long_oi",
                        "short_oi",
                        "net_oi",
                        "long_oi_amount",
                        "short_oi_amount",
                        "net_oi_amount",
                    )
                }
                values.update(
                    {
                        "product_id": product.id,
                        "institution_type": row.institution_type.value,
                        **self._meta(row, run_id),
                    }
                )
                model, where = (
                    InstitutionFuturesPositionModel,
                    (
                        InstitutionFuturesPositionModel.product_id == product.id,
                        InstitutionFuturesPositionModel.trade_date == row.trade_date,
                        InstitutionFuturesPositionModel.institution_type
                        == row.institution_type.value,
                    ),
                )
            elif isinstance(row, TraderConcentration):
                product = await self._product(row.product_code)
                if not product:
                    raise LookupError(f"missing product {row.product_code}")
                values = {
                    "product_id": product.id,
                    "trade_date": row.trade_date,
                    "contract_scope": row.contract_scope,
                    "side": row.side.value,
                    "top_n": row.top_n,
                    "open_interest": row.open_interest,
                    "market_open_interest": row.market_open_interest,
                    "concentration_ratio": row.concentration_ratio,
                    "specific_institution_oi": row.specific_institution_oi,
                    **self._meta(row, run_id),
                }
                model, where = (
                    TraderConcentrationModel,
                    (
                        TraderConcentrationModel.product_id == product.id,
                        TraderConcentrationModel.trade_date == row.trade_date,
                        TraderConcentrationModel.contract_scope == row.contract_scope,
                        TraderConcentrationModel.side == row.side.value,
                        TraderConcentrationModel.top_n == row.top_n,
                    ),
                )
            elif isinstance(row, OptionPutCallRatio):
                values = {
                    name: getattr(row, name)
                    for name in (
                        "product_code",
                        "trade_date",
                        "put_volume",
                        "call_volume",
                        "volume_put_call_ratio",
                        "put_open_interest",
                        "call_open_interest",
                        "oi_put_call_ratio",
                    )
                }
                values.update(self._meta(row, run_id))
                model, where = (
                    OptionPutCallRatioModel,
                    (
                        OptionPutCallRatioModel.product_code == row.product_code,
                        OptionPutCallRatioModel.trade_date == row.trade_date,
                    ),
                )
            elif isinstance(row, OptionStrikeOpenInterest):
                values = {
                    name: getattr(row, name)
                    for name in (
                        "product_code",
                        "expiry",
                        "trade_date",
                        "strike",
                        "open_interest",
                        "volume",
                        "settlement_price",
                    )
                }
                values.update({"option_type": row.option_type.value, **self._meta(row, run_id)})
                model, where = (
                    OptionStrikeOpenInterestModel,
                    (
                        OptionStrikeOpenInterestModel.product_code == row.product_code,
                        OptionStrikeOpenInterestModel.expiry == row.expiry,
                        OptionStrikeOpenInterestModel.trade_date == row.trade_date,
                        OptionStrikeOpenInterestModel.option_type == row.option_type.value,
                        OptionStrikeOpenInterestModel.strike == row.strike,
                    ),
                )
            elif isinstance(row, VolatilityIndex):
                values = {
                    name: getattr(row, name)
                    for name in ("code", "trade_date", "open", "high", "low", "close")
                }
                values.update(self._meta(row, run_id))
                model, where = (
                    VolatilityIndexModel,
                    (
                        VolatilityIndexModel.code == row.code,
                        VolatilityIndexModel.trade_date == row.trade_date,
                    ),
                )
            else:
                raise TypeError(f"unsupported {dataset}: {type(row)}")
            add, change = await self._upsert(model, where, values)
            inserted += add
            updated += change
        await self.session.flush()
        return inserted, updated

    @staticmethod
    def _metadata(row):
        return SourceMetadata(
            row.source_code,
            row.as_of,
            row.received_at,
            DataStatus(row.data_status),
            row.source_revision,
            row.ingestion_run_id,
        )

    async def products(self, product_code=None):
        q = select(FuturesProductModel)
        if product_code:
            q = q.where(FuturesProductModel.code == product_code)
        rows = (await self.session.scalars(q.order_by(FuturesProductModel.code))).all()
        return [
            FuturesProduct(
                r.code,
                r.name,
                r.contract_multiplier,
                r.currency,
                SessionType(r.session_type),
                r.is_active,
            )
            for r in rows
        ]

    async def contracts(self, product_code):
        rows = (
            await self.session.execute(
                select(FuturesContractModel, FuturesProductModel)
                .join(FuturesProductModel)
                .where(FuturesProductModel.code == product_code)
                .order_by(FuturesContractModel.contract_month)
            )
        ).all()
        return [
            FuturesContract(
                p.code,
                r.contract_code,
                r.contract_month,
                r.expiry_date,
                r.last_trade_date,
                ContractStatus(r.status),
                r.is_active,
            )
            for r, p in rows
        ]

    async def daily(self, product_code, contract_code, limit):
        q = (
            select(FuturesDailyPriceModel, FuturesContractModel, FuturesProductModel)
            .select_from(FuturesDailyPriceModel)
            .join(
                FuturesContractModel,
                FuturesDailyPriceModel.contract_id == FuturesContractModel.id,
            )
            .join(FuturesProductModel, FuturesContractModel.product_id == FuturesProductModel.id)
            .where(FuturesProductModel.code == product_code)
        )
        if contract_code:
            q = q.where(FuturesContractModel.contract_code == contract_code)
        rows = (
            await self.session.execute(
                q.order_by(FuturesDailyPriceModel.trade_date.desc()).limit(limit)
            )
        ).all()
        return list(
            reversed(
                [
                    FuturesDailyPrice(
                        p.code,
                        c.contract_code,
                        c.contract_month,
                        r.trade_date,
                        SessionType(r.session_type),
                        r.open,
                        r.high,
                        r.low,
                        r.close,
                        r.settlement_price,
                        r.change,
                        r.change_percent,
                        r.volume,
                        r.open_interest,
                        self._metadata(r),
                    )
                    for r, c, p in rows
                ]
            )
        )

    async def positions(self, product_code, limit):
        rows = (
            await self.session.execute(
                select(InstitutionFuturesPositionModel, FuturesProductModel)
                .join(FuturesProductModel)
                .where(FuturesProductModel.code == product_code)
                .order_by(InstitutionFuturesPositionModel.trade_date.desc())
                .limit(limit * 3)
            )
        ).all()
        return list(
            reversed(
                [
                    InstitutionFuturesPosition(
                        p.code,
                        r.trade_date,
                        InstitutionType(r.institution_type),
                        r.long_volume,
                        r.short_volume,
                        r.net_volume,
                        r.long_amount,
                        r.short_amount,
                        r.net_amount,
                        r.long_oi,
                        r.short_oi,
                        r.net_oi,
                        r.long_oi_amount,
                        r.short_oi_amount,
                        r.net_oi_amount,
                        self._metadata(r),
                    )
                    for r, p in rows
                ]
            )
        )

    async def concentrations(self, product_code, limit):
        rows = (
            await self.session.execute(
                select(TraderConcentrationModel, FuturesProductModel)
                .join(FuturesProductModel)
                .where(FuturesProductModel.code == product_code)
                .order_by(TraderConcentrationModel.trade_date.desc())
                .limit(limit * 4)
            )
        ).all()
        return list(
            reversed(
                [
                    TraderConcentration(
                        p.code,
                        r.trade_date,
                        r.contract_scope,
                        PositionSide(r.side),
                        r.top_n,
                        r.open_interest,
                        r.market_open_interest,
                        r.concentration_ratio,
                        r.specific_institution_oi,
                        self._metadata(r),
                    )
                    for r, p in rows
                ]
            )
        )

    async def put_call(self, product_code, limit):
        rows = (
            await self.session.scalars(
                select(OptionPutCallRatioModel)
                .where(OptionPutCallRatioModel.product_code == product_code)
                .order_by(OptionPutCallRatioModel.trade_date.desc())
                .limit(limit)
            )
        ).all()
        return list(
            reversed(
                [
                    OptionPutCallRatio(
                        r.product_code,
                        r.trade_date,
                        r.put_volume,
                        r.call_volume,
                        r.volume_put_call_ratio,
                        r.put_open_interest,
                        r.call_open_interest,
                        r.oi_put_call_ratio,
                        self._metadata(r),
                    )
                    for r in rows
                ]
            )
        )

    async def strike_oi(self, product_code, expiry, trade_date):
        q = select(OptionStrikeOpenInterestModel).where(
            OptionStrikeOpenInterestModel.product_code == product_code
        )
        if expiry:
            q = q.where(OptionStrikeOpenInterestModel.expiry == expiry)
        if trade_date:
            q = q.where(OptionStrikeOpenInterestModel.trade_date == trade_date)
        rows = (await self.session.scalars(q.order_by(OptionStrikeOpenInterestModel.strike))).all()
        return [
            OptionStrikeOpenInterest(
                r.product_code,
                r.expiry,
                r.trade_date,
                OptionType(r.option_type),
                r.strike,
                r.open_interest,
                r.volume,
                r.settlement_price,
                self._metadata(r),
            )
            for r in rows
        ]

    async def volatility(self, code, limit):
        rows = (
            await self.session.scalars(
                select(VolatilityIndexModel)
                .where(VolatilityIndexModel.code == code)
                .order_by(VolatilityIndexModel.trade_date.desc())
                .limit(limit)
            )
        ).all()
        return list(
            reversed(
                [
                    VolatilityIndex(
                        r.code, r.trade_date, r.open, r.high, r.low, r.close, self._metadata(r)
                    )
                    for r in rows
                ]
            )
        )
