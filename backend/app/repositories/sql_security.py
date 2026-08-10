from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode, Security, SecurityRecord, SecurityStatus, SecurityType
from app.repositories.models import IndustryModel, MarketModel, SecurityIndustryModel, SecurityModel


class SqlSecurityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def synchronize(
        self, market: MarketCode, records: list[SecurityRecord], run_id: UUID
    ) -> tuple[int, int, int]:
        market_model = await self.session.scalar(
            select(MarketModel).where(MarketModel.code == market.value)
        )
        if market_model is None:
            market_model = MarketModel(
                code=market.value,
                name="臺灣證券交易所" if market is MarketCode.TWSE else "證券櫃檯買賣中心",
            )
            self.session.add(market_model)
            await self.session.flush()
        existing = {
            row.code: row
            for row in (
                await self.session.scalars(
                    select(SecurityModel).where(SecurityModel.market_id == market_model.id)
                )
            ).all()
        }
        inserted = updated = 0
        seen: set[str] = set()
        now = datetime.now(UTC)
        for record in records:
            if record.code in seen:
                raise ValueError(f"duplicate security in {market.value}: {record.code}")
            seen.add(record.code)
            model = existing.get(record.code)
            values = (
                record.name,
                record.security_type.value,
                record.status.value,
                record.listing_date,
                record.source_code,
                record.as_of,
                record.received_at,
                record.data_status,
                record.source_revision,
            )
            if model is None:
                model = SecurityModel(
                    market_id=market_model.id,
                    code=record.code,
                    name=record.name,
                    security_type=record.security_type.value,
                    status=record.status.value,
                    is_active=record.status is SecurityStatus.ACTIVE,
                    listing_date=record.listing_date,
                    source_code=record.source_code,
                    as_of=record.as_of,
                    received_at=record.received_at,
                    data_status=record.data_status,
                    source_revision=record.source_revision,
                    ingestion_run_id=run_id,
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(model)
                await self.session.flush()
                inserted += 1
            else:
                before = (
                    model.name,
                    model.security_type,
                    model.status,
                    model.listing_date,
                    model.source_code,
                    model.as_of,
                    model.received_at,
                    model.data_status,
                    model.source_revision,
                )
                if before != values or not model.is_active:
                    (
                        model.name,
                        model.security_type,
                        model.status,
                        model.listing_date,
                        model.source_code,
                        model.as_of,
                        model.received_at,
                        model.data_status,
                        model.source_revision,
                    ) = values
                    model.is_active = record.status is SecurityStatus.ACTIVE
                    model.ingestion_run_id = run_id
                    model.updated_at = now
                    updated += 1
            await self._set_industry(model.id, record)
        inactive = 0
        for code, model in existing.items():
            if code not in seen and model.is_active:
                model.is_active = False
                model.status = SecurityStatus.INACTIVE.value
                model.ingestion_run_id = run_id
                model.updated_at = now
                inactive += 1
        await self.session.flush()
        return inserted, updated, inactive

    async def _set_industry(self, security_id: UUID, record: SecurityRecord) -> None:
        if record.industry is None:
            return
        industry = await self.session.scalar(
            select(IndustryModel).where(
                IndustryModel.classification_source == record.industry.classification_source,
                IndustryModel.code == record.industry.code,
            )
        )
        if industry is None:
            industry = IndustryModel(
                code=record.industry.code,
                name=record.industry.name,
                classification_source=record.industry.classification_source,
            )
            self.session.add(industry)
            await self.session.flush()
        elif industry.name != record.industry.name:
            industry.name = record.industry.name
        await self.session.execute(
            SecurityIndustryModel.__table__.delete().where(
                SecurityIndustryModel.security_id == security_id
            )
        )
        self.session.add(
            SecurityIndustryModel(security_id=security_id, industry_id=industry.id, is_primary=True)
        )

    def _base_query(self):
        return (
            select(SecurityModel, MarketModel.code, IndustryModel.name)
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .outerjoin(
                SecurityIndustryModel,
                and_(
                    SecurityIndustryModel.security_id == SecurityModel.id,
                    SecurityIndustryModel.is_primary.is_(True),
                ),
            )
            .outerjoin(IndustryModel, IndustryModel.id == SecurityIndustryModel.industry_id)
        )

    async def search(self, query: str, market: MarketCode | None, limit: int) -> list[Security]:
        pattern = f"%{query}%"
        statement = self._base_query().where(
            SecurityModel.is_active.is_(True),
            SecurityModel.security_type == SecurityType.COMMON_STOCK.value,
            or_(SecurityModel.code.ilike(f"{query}%"), SecurityModel.name.ilike(pattern)),
        )
        if market:
            statement = statement.where(MarketModel.code == market.value)
        statement = statement.order_by(
            case(
                (SecurityModel.code == query, 0),
                (SecurityModel.code.ilike(f"{query}%"), 1),
                else_=2,
            ),
            func.similarity(SecurityModel.name, query).desc(),
            SecurityModel.code,
        ).limit(limit)
        return [self._to_domain(*row) for row in (await self.session.execute(statement)).all()]

    async def find_by_code(self, code: str, market: MarketCode | None) -> list[Security]:
        statement = self._base_query().where(
            SecurityModel.code == code, SecurityModel.is_active.is_(True)
        )
        if market:
            statement = statement.where(MarketModel.code == market.value)
        return [self._to_domain(*row) for row in (await self.session.execute(statement)).all()]

    @staticmethod
    def _to_domain(model: SecurityModel, market: str, industry: str | None) -> Security:
        return Security(
            id=model.id,
            market=MarketCode(market),
            code=model.code,
            name=model.name,
            security_type=SecurityType(model.security_type),
            status=SecurityStatus(model.status),
            is_active=model.is_active,
            listing_date=model.listing_date,
            primary_industry=industry,
            source_code=model.source_code,
            as_of=model.as_of,
            received_at=model.received_at,
            data_status=DataStatus(model.data_status),
        )
