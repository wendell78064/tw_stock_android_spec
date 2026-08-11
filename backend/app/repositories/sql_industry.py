from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.industry import IndustryInfo, MemberSecurity, ThemeInfo
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode, SecurityType
from app.repositories.models import (
    DailyPriceModel,
    IndustryModel,
    MarketModel,
    SecurityIndustryModel,
    SecurityModel,
    SecurityThemeModel,
    ThemeModel,
)


class SqlIndustryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_industries(self) -> list[IndustryInfo]:
        statement = (
            select(
                IndustryModel,
                func.count(SecurityIndustryModel.security_id).label("member_count"),
            )
            .outerjoin(
                SecurityIndustryModel,
                IndustryModel.id == SecurityIndustryModel.industry_id,
            )
            .outerjoin(
                SecurityModel,
                (SecurityIndustryModel.security_id == SecurityModel.id)
                & (SecurityModel.is_active.is_(True)),
            )
            .group_by(IndustryModel.id)
            .order_by(IndustryModel.name)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            IndustryInfo(
                id=ind.id,
                code=ind.code,
                name=ind.name,
                classification_source=ind.classification_source,
                member_count=count,
            )
            for ind, count in rows
        ]

    async def get_industry(self, industry_id: UUID) -> IndustryInfo | None:
        statement = (
            select(
                IndustryModel,
                func.count(SecurityIndustryModel.security_id).label("member_count"),
            )
            .outerjoin(
                SecurityIndustryModel,
                IndustryModel.id == SecurityIndustryModel.industry_id,
            )
            .outerjoin(
                SecurityModel,
                (SecurityIndustryModel.security_id == SecurityModel.id)
                & (SecurityModel.is_active.is_(True)),
            )
            .where(IndustryModel.id == industry_id)
            .group_by(IndustryModel.id)
        )
        row = (await self.session.execute(statement)).first()
        if not row:
            return None
        ind, count = row
        return IndustryInfo(
            id=ind.id,
            code=ind.code,
            name=ind.name,
            classification_source=ind.classification_source,
            member_count=count,
        )

    async def list_industry_securities(
        self, industry_id: UUID
    ) -> tuple[IndustryInfo, list[MemberSecurity], datetime, DataStatus]:
        industry = await self.get_industry(industry_id)
        if industry is None:
            raise LookupError("Industry not found")

        statement = (
            select(SecurityModel, MarketModel.code)
            .join(
                SecurityIndustryModel,
                SecurityIndustryModel.security_id == SecurityModel.id,
            )
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(
                SecurityIndustryModel.industry_id == industry_id,
                SecurityModel.is_active.is_(True),
            )
            .order_by(SecurityModel.code)
        )
        rows = (await self.session.execute(statement)).all()
        securities = [row[0] for row in rows]
        markets = {row[0].id: row[1] for row in rows}

        members, as_of, status = await self._bulk_enrich_members(securities, markets)
        return industry, members, as_of, status

    async def list_themes(self) -> list[ThemeInfo]:
        statement = (
            select(
                ThemeModel,
                func.count(SecurityThemeModel.security_id).label("member_count"),
            )
            .outerjoin(
                SecurityThemeModel,
                ThemeModel.id == SecurityThemeModel.theme_id,
            )
            .outerjoin(
                SecurityModel,
                (SecurityThemeModel.security_id == SecurityModel.id)
                & (SecurityModel.is_active.is_(True)),
            )
            .group_by(ThemeModel.id)
            .order_by(ThemeModel.name)
        )
        rows = (await self.session.execute(statement)).all()
        return [
            ThemeInfo(
                id=theme.id,
                code=theme.code,
                name=theme.name,
                description=theme.description,
                classification_type=theme.classification_type,
                member_count=count,
                created_at=theme.created_at,
                updated_at=theme.updated_at,
            )
            for theme, count in rows
        ]

    async def get_theme(self, theme_id: UUID) -> ThemeInfo | None:
        statement = (
            select(
                ThemeModel,
                func.count(SecurityThemeModel.security_id).label("member_count"),
            )
            .outerjoin(
                SecurityThemeModel,
                ThemeModel.id == SecurityThemeModel.theme_id,
            )
            .outerjoin(
                SecurityModel,
                (SecurityThemeModel.security_id == SecurityModel.id)
                & (SecurityModel.is_active.is_(True)),
            )
            .where(ThemeModel.id == theme_id)
            .group_by(ThemeModel.id)
        )
        row = (await self.session.execute(statement)).first()
        if not row:
            return None
        theme, count = row
        return ThemeInfo(
            id=theme.id,
            code=theme.code,
            name=theme.name,
            description=theme.description,
            classification_type=theme.classification_type,
            member_count=count,
            created_at=theme.created_at,
            updated_at=theme.updated_at,
        )

    async def list_theme_securities(
        self, theme_id: UUID
    ) -> tuple[ThemeInfo, list[MemberSecurity], datetime, DataStatus]:
        theme = await self.get_theme(theme_id)
        if theme is None:
            raise LookupError("Theme not found")

        statement = (
            select(SecurityModel, MarketModel.code)
            .join(
                SecurityThemeModel,
                SecurityThemeModel.security_id == SecurityModel.id,
            )
            .join(MarketModel, MarketModel.id == SecurityModel.market_id)
            .where(
                SecurityThemeModel.theme_id == theme_id,
                SecurityModel.is_active.is_(True),
            )
            .order_by(SecurityModel.code)
        )
        rows = (await self.session.execute(statement)).all()
        securities = [row[0] for row in rows]
        markets = {row[0].id: row[1] for row in rows}

        members, as_of, status = await self._bulk_enrich_members(securities, markets)
        return theme, members, as_of, status

    async def create_theme(
        self, code: str, name: str, description: str | None, classification_type: str
    ) -> ThemeInfo:
        now = datetime.now(UTC)
        theme = ThemeModel(
            code=code,
            name=name,
            description=description,
            classification_type=classification_type,
            created_at=now,
            updated_at=now,
        )
        self.session.add(theme)
        await self.session.flush()
        return ThemeInfo(
            id=theme.id,
            code=theme.code,
            name=theme.name,
            description=theme.description,
            classification_type=theme.classification_type,
            member_count=0,
            created_at=theme.created_at,
            updated_at=theme.updated_at,
        )

    async def update_theme(
        self, theme_id: UUID, name: str | None, description: str | None
    ) -> ThemeInfo | None:
        theme = await self.session.get(ThemeModel, theme_id)
        if theme is None:
            return None
        if name is not None:
            theme.name = name
        if description is not None:
            theme.description = description
        theme.updated_at = datetime.now(UTC)
        await self.session.flush()
        return await self.get_theme(theme_id)

    async def delete_theme(self, theme_id: UUID) -> bool:
        theme = await self.session.get(ThemeModel, theme_id)
        if theme is None:
            return False
        await self.session.delete(theme)
        await self.session.flush()
        return True

    async def add_theme_security(self, theme_id: UUID, security_id: UUID) -> bool:
        theme = await self.session.get(ThemeModel, theme_id)
        security = await self.session.get(SecurityModel, security_id)
        if theme is None or security is None:
            return False
        existing = await self.session.get(
            SecurityThemeModel, {"security_id": security_id, "theme_id": theme_id}
        )
        if existing is not None:
            return True
        mapping = SecurityThemeModel(
            security_id=security_id, theme_id=theme_id, created_at=datetime.now(UTC)
        )
        self.session.add(mapping)
        await self.session.flush()
        return True

    async def remove_theme_security(self, theme_id: UUID, security_id: UUID) -> bool:
        mapping = await self.session.get(
            SecurityThemeModel, {"security_id": security_id, "theme_id": theme_id}
        )
        if mapping is None:
            return False
        await self.session.delete(mapping)
        await self.session.flush()
        return True

    async def _bulk_enrich_members(
        self, securities: list[SecurityModel], markets: dict[UUID, str]
    ) -> tuple[list[MemberSecurity], datetime, DataStatus]:
        if not securities:
            now = datetime.now(UTC)
            return [], now, DataStatus.UNAVAILABLE

        sec_ids = [sec.id for sec in securities]
        # Window query to get latest 2 daily prices per security
        subq = (
            select(
                DailyPriceModel,
                func.row_number()
                .over(
                    partition_by=DailyPriceModel.security_id,
                    order_by=DailyPriceModel.trade_date.desc(),
                )
                .label("rn"),
            )
            .where(DailyPriceModel.security_id.in_(sec_ids))
            .subquery()
        )

        stmt = select(subq).where(subq.c.rn <= 2)
        price_rows = (await self.session.execute(stmt)).all()

        prices_by_sec: dict[UUID, list[DailyPriceModel]] = {sec_id: [] for sec_id in sec_ids}
        for row in price_rows:
            # Map subquery row back to price object or attributes
            sec_id = row.security_id
            prices_by_sec[sec_id].append(row)

        members: list[MemberSecurity] = []
        all_as_of: list[datetime] = []
        statuses: set[DataStatus] = set()

        for sec in securities:
            sec_prices = prices_by_sec.get(sec.id, [])
            sec_prices.sort(key=lambda p: p.trade_date, reverse=True)

            close_val: Decimal | None = None
            change_val: Decimal | None = None
            change_pct_val: Decimal | None = None
            sec_as_of: datetime | None = None
            sec_status: DataStatus = sec.data_status

            if sec_prices:
                latest = sec_prices[0]
                close_val = Decimal(str(latest.close)) if latest.close is not None else None
                sec_as_of = latest.as_of
                sec_status = latest.data_status
                all_as_of.append(latest.as_of)
                statuses.add(latest.data_status)

                if len(sec_prices) >= 2 and close_val is not None:
                    prev = sec_prices[1]
                    prev_close = Decimal(str(prev.close)) if prev.close is not None else None
                    if prev_close is not None and prev_close != Decimal("0"):
                        change_val = close_val - prev_close
                        change_pct_val = (
                            (change_val / prev_close) * Decimal("100")
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                all_as_of.append(sec.as_of)
                statuses.add(sec.data_status)

            members.append(
                MemberSecurity(
                    security_id=sec.id,
                    code=sec.code,
                    name=sec.name,
                    market=MarketCode(markets[sec.id]),
                    security_type=SecurityType(sec.security_type),
                    is_active=sec.is_active,
                    close=close_val,
                    change=change_val,
                    change_percent=change_pct_val,
                    as_of=sec_as_of or sec.as_of,
                    data_status=sec_status,
                )
            )

        max_as_of = max(all_as_of) if all_as_of else datetime.now(UTC)
        agg_status = (
            statuses.pop()
            if len(statuses) == 1
            else (DataStatus.PARTIAL if len(statuses) > 1 else DataStatus.UNAVAILABLE)
        )
        return members, max_as_of, agg_status
