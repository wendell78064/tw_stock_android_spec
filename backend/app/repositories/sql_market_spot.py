from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_data import DataStatus
from app.domain.market_spot import (
    DealerSubtype,
    InstitutionalRecord,
    InstitutionType,
    LendingRecord,
    MarginRecord,
    MarketBreadthRecord,
    MarketIndexRecord,
    SourceMetadata,
)
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode
from app.repositories.models import (
    InstitutionSpotTradingModel,
    MarginTradingModel,
    MarketBreadthModel,
    MarketIndexDailyModel,
    MarketIndexModel,
    MarketInstitutionalSpotModel,
    MarketMarginTradingModel,
    MarketModel,
    MarketSecuritiesLendingModel,
    SecuritiesLendingModel,
    SecurityModel,
)


class SqlMarketSpotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _security_id(self, key: SecurityKey) -> UUID | None:
        return await self.session.scalar(
            select(SecurityModel.id)
            .join(MarketModel)
            .where(MarketModel.code == key.market.value, SecurityModel.code == key.code)
        )

    @staticmethod
    def _meta(record, run_id: UUID) -> dict:
        meta = record.metadata
        return {
            "source_code": meta.source_code,
            "as_of": meta.as_of,
            "received_at": meta.received_at,
            "data_status": meta.data_status,
            "source_revision": meta.source_revision,
            "ingestion_run_id": run_id,
        }

    async def _upsert(self, model_type, where, values: dict) -> tuple[int, int]:
        model = await self.session.scalar(select(model_type).where(*where))
        if model is None:
            self.session.add(model_type(**values))
            return 1, 0
        comparable = {
            key: value for key, value in values.items() if key not in {"id", "ingestion_run_id"}
        }
        if any(getattr(model, key) != value for key, value in comparable.items()):
            for key, value in values.items():
                setattr(model, key, value)
            return 0, 1
        return 0, 0

    async def synchronize(
        self, dataset: str, records: list[object], run_id: UUID
    ) -> tuple[int, int]:
        inserted = updated = 0
        seen = set()
        for record in records:
            if isinstance(record, MarketIndexRecord):
                master = await self.session.scalar(
                    select(MarketIndexModel).where(
                        MarketIndexModel.market_code == record.market.value,
                        MarketIndexModel.code == record.code,
                    )
                )
                if master is None:
                    master = MarketIndexModel(
                        code=record.code,
                        name=record.name,
                        market_code=record.market.value,
                        is_active=True,
                    )
                    self.session.add(master)
                    await self.session.flush()
                identity = (record.market, record.code, record.trade_date)
                values = {
                    "index_id": master.id,
                    "trade_date": record.trade_date,
                    "open": record.open,
                    "high": record.high,
                    "low": record.low,
                    "close": record.close,
                    "change": record.change,
                    "change_percent": record.change_percent,
                    "turnover_amount": record.turnover_amount,
                    "volume": record.volume,
                    **self._meta(record, run_id),
                }
                model, where = (
                    MarketIndexDailyModel,
                    (
                        MarketIndexDailyModel.index_id == master.id,
                        MarketIndexDailyModel.trade_date == record.trade_date,
                    ),
                )
            elif isinstance(record, MarketBreadthRecord):
                identity = (record.market, record.trade_date)
                values = {
                    "market_code": record.market.value,
                    "trade_date": record.trade_date,
                    "advancers": record.advancers,
                    "decliners": record.decliners,
                    "unchanged": record.unchanged,
                    "limit_up": record.limit_up,
                    "limit_down": record.limit_down,
                    "total_traded": record.total_traded,
                    "turnover_amount": record.turnover_amount,
                    **self._meta(record, run_id),
                }
                model, where = (
                    MarketBreadthModel,
                    (
                        MarketBreadthModel.market_code == record.market.value,
                        MarketBreadthModel.trade_date == record.trade_date,
                    ),
                )
            elif isinstance(record, InstitutionalRecord):
                subtype = record.dealer_subtype.value if record.dealer_subtype else "NONE"
                identity = (
                    record.security,
                    record.market,
                    record.trade_date,
                    record.institution_type,
                    subtype,
                )
                if record.security:
                    security_id = await self._security_id(record.security)
                    if security_id is None:
                        # Official trading reports can retain an instrument absent from the
                        # active common-stock master. It must not create an orphan or abort
                        # the otherwise valid market dataset.
                        continue
                    values = {
                        "security_id": security_id,
                        "trade_date": record.trade_date,
                        "institution_type": record.institution_type.value,
                        "dealer_subtype": subtype,
                        "buy_shares": record.buy,
                        "sell_shares": record.sell,
                        "net_shares": record.net,
                        "buy_amount": None,
                        "sell_amount": None,
                        "net_amount": None,
                        **self._meta(record, run_id),
                    }
                    model, where = (
                        InstitutionSpotTradingModel,
                        (
                            InstitutionSpotTradingModel.security_id == security_id,
                            InstitutionSpotTradingModel.trade_date == record.trade_date,
                            InstitutionSpotTradingModel.institution_type
                            == record.institution_type.value,
                            InstitutionSpotTradingModel.dealer_subtype == subtype,
                        ),
                    )
                else:
                    values = {
                        "market_code": record.market.value,
                        "trade_date": record.trade_date,
                        "institution_type": record.institution_type.value,
                        "dealer_subtype": subtype,
                        "buy_amount": record.buy,
                        "sell_amount": record.sell,
                        "net_amount": record.net,
                        **self._meta(record, run_id),
                    }
                    model, where = (
                        MarketInstitutionalSpotModel,
                        (
                            MarketInstitutionalSpotModel.market_code == record.market.value,
                            MarketInstitutionalSpotModel.trade_date == record.trade_date,
                            MarketInstitutionalSpotModel.institution_type
                            == record.institution_type.value,
                            MarketInstitutionalSpotModel.dealer_subtype == subtype,
                        ),
                    )
            elif isinstance(record, MarginRecord):
                identity = (record.security, record.market, record.trade_date)
                values = {
                    name: getattr(record, name)
                    for name in (
                        "margin_buy",
                        "margin_sell",
                        "margin_cash_repayment",
                        "margin_balance",
                        "margin_balance_change",
                        "short_sell",
                        "short_cover",
                        "short_stock_repayment",
                        "short_balance",
                        "short_balance_change",
                        "short_margin_ratio",
                    )
                }
                values.update({"trade_date": record.trade_date, **self._meta(record, run_id)})
                if record.security:
                    security_id = await self._security_id(record.security)
                    if security_id is None:
                        continue
                    values.update(
                        {
                            "security_id": security_id,
                            "margin_utilization": record.margin_utilization,
                            "short_utilization": record.short_utilization,
                        }
                    )
                    model, where = (
                        MarginTradingModel,
                        (
                            MarginTradingModel.security_id == security_id,
                            MarginTradingModel.trade_date == record.trade_date,
                        ),
                    )
                else:
                    values["market_code"] = record.market.value
                    model, where = (
                        MarketMarginTradingModel,
                        (
                            MarketMarginTradingModel.market_code == record.market.value,
                            MarketMarginTradingModel.trade_date == record.trade_date,
                        ),
                    )
            elif isinstance(record, LendingRecord):
                identity = (record.security, record.market, record.trade_date)
                values = {
                    "trade_date": record.trade_date,
                    "lending_sell": record.lending_sell,
                    "lending_return": record.lending_return,
                    "lending_balance": record.lending_balance,
                    "lending_balance_change": record.lending_balance_change,
                    **self._meta(record, run_id),
                }
                if record.security:
                    security_id = await self._security_id(record.security)
                    if security_id is None:
                        continue
                    values["security_id"] = security_id
                    model, where = (
                        SecuritiesLendingModel,
                        (
                            SecuritiesLendingModel.security_id == security_id,
                            SecuritiesLendingModel.trade_date == record.trade_date,
                        ),
                    )
                else:
                    values["market_code"] = record.market.value
                    model, where = (
                        MarketSecuritiesLendingModel,
                        (
                            MarketSecuritiesLendingModel.market_code == record.market.value,
                            MarketSecuritiesLendingModel.trade_date == record.trade_date,
                        ),
                    )
            else:
                raise TypeError(f"unsupported {dataset} record")
            if identity in seen:
                raise ValueError(f"duplicate {dataset}: {identity}")
            seen.add(identity)
            add, change = await self._upsert(model, where, values)
            inserted += add
            updated += change
        await self.session.flush()
        return inserted, updated

    @staticmethod
    def _metadata(item) -> SourceMetadata:
        return SourceMetadata(
            item.source_code,
            item.as_of,
            item.received_at,
            DataStatus(item.data_status),
            item.source_revision,
            item.ingestion_run_id,
        )

    async def indexes(self, code, start, end, limit=None):
        statement = select(MarketIndexDailyModel, MarketIndexModel).join(MarketIndexModel)
        if code:
            statement = statement.where(MarketIndexModel.code == code)
        if start:
            statement = statement.where(MarketIndexDailyModel.trade_date >= start)
        if end:
            statement = statement.where(MarketIndexDailyModel.trade_date <= end)
        statement = statement.order_by(MarketIndexDailyModel.trade_date.desc())
        if limit:
            statement = statement.limit(limit)
        rows = (await self.session.execute(statement)).all()
        return list(
            reversed(
                [
                    MarketIndexRecord(
                        master.code,
                        master.name,
                        MarketCode(master.market_code),
                        item.trade_date,
                        item.open,
                        item.high,
                        item.low,
                        item.close,
                        item.change,
                        item.change_percent,
                        item.turnover_amount,
                        item.volume,
                        self._metadata(item),
                    )
                    for item, master in rows
                ]
            )
        )

    async def breadth(self, market, start, end):
        statement = select(MarketBreadthModel)
        if market:
            statement = statement.where(MarketBreadthModel.market_code == market.value)
        if start:
            statement = statement.where(MarketBreadthModel.trade_date >= start)
        if end:
            statement = statement.where(MarketBreadthModel.trade_date <= end)
        items = (
            await self.session.scalars(statement.order_by(MarketBreadthModel.trade_date))
        ).all()
        return [
            MarketBreadthRecord(
                MarketCode(i.market_code),
                i.trade_date,
                i.advancers,
                i.decliners,
                i.unchanged,
                i.limit_up,
                i.limit_down,
                i.total_traded,
                i.turnover_amount,
                self._metadata(i),
            )
            for i in items
        ]

    async def institutional(self, market, security, start, end, institution=None):
        if security:
            security_id = await self._security_id(security)
            model = InstitutionSpotTradingModel
            statement = select(model).where(model.security_id == security_id)
        else:
            model = MarketInstitutionalSpotModel
            statement = select(model).where(model.market_code == market.value)
        if start:
            statement = statement.where(model.trade_date >= start)
        if end:
            statement = statement.where(model.trade_date <= end)
        if institution:
            statement = statement.where(model.institution_type == institution.value)
        items = (await self.session.scalars(statement.order_by(model.trade_date))).all()
        return [
            InstitutionalRecord(
                market,
                i.trade_date,
                InstitutionType(i.institution_type),
                None if i.dealer_subtype == "NONE" else DealerSubtype(i.dealer_subtype),
                i.buy_shares if security else i.buy_amount,
                i.sell_shares if security else i.sell_amount,
                i.net_shares if security else i.net_amount,
                self._metadata(i),
                security,
                not bool(security),
            )
            for i in items
        ]

    async def margins(self, market, security, start, end):
        if security:
            security_id = await self._security_id(security)
            model = MarginTradingModel
            statement = select(model).where(model.security_id == security_id)
        else:
            model = MarketMarginTradingModel
            statement = select(model).where(model.market_code == market.value)
        if start:
            statement = statement.where(model.trade_date >= start)
        if end:
            statement = statement.where(model.trade_date <= end)
        items = (await self.session.scalars(statement.order_by(model.trade_date))).all()
        return [
            MarginRecord(
                market,
                i.trade_date,
                i.margin_buy,
                i.margin_sell,
                i.margin_cash_repayment,
                i.margin_balance,
                i.margin_balance_change,
                i.short_sell,
                i.short_cover,
                i.short_stock_repayment,
                i.short_balance,
                i.short_balance_change,
                i.short_margin_ratio,
                self._metadata(i),
                security,
                getattr(i, "margin_utilization", None),
                getattr(i, "short_utilization", None),
            )
            for i in items
        ]

    async def lending(self, market, security, start, end):
        if security:
            security_id = await self._security_id(security)
            model = SecuritiesLendingModel
            statement = select(model).where(model.security_id == security_id)
        else:
            model = MarketSecuritiesLendingModel
            statement = select(model).where(model.market_code == market.value)
        if start:
            statement = statement.where(model.trade_date >= start)
        if end:
            statement = statement.where(model.trade_date <= end)
        items = (await self.session.scalars(statement.order_by(model.trade_date))).all()
        return [
            LendingRecord(
                market,
                i.trade_date,
                i.lending_sell,
                i.lending_return,
                i.lending_balance,
                i.lending_balance_change,
                self._metadata(i),
                security,
            )
            for i in items
        ]
