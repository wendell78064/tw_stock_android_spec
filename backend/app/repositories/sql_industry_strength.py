from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.industry_strength import (
    ALGORITHM_VERSION,
    StrengthComponents,
    TaxonomyLeader,
    TaxonomyStrengthDetail,
    TaxonomyStrengthSnapshot,
)
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode
from app.repositories.models import (
    DailyPriceModel,
    IndustryModel,
    InstitutionalSpotModel,
    SecurityIndustryModel,
    SecurityModel,
    SecurityThemeModel,
    TaxonomyStrengthSnapshotModel,
    ThemeModel,
)


class SqlIndustryStrengthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_industry_strengths(
        self,
        window: int = 20,
        trade_date: date | None = None,
        sort_by: str = "strength",
    ) -> list[TaxonomyStrengthSnapshot]:
        return await self._get_taxonomy_strengths(
            is_industry=True, window=window, trade_date=trade_date, sort_by=sort_by
        )

    async def get_theme_strengths(
        self,
        window: int = 20,
        trade_date: date | None = None,
        sort_by: str = "strength",
    ) -> list[TaxonomyStrengthSnapshot]:
        return await self._get_taxonomy_strengths(
            is_industry=False, window=window, trade_date=trade_date, sort_by=sort_by
        )

    async def _get_taxonomy_strengths(
        self,
        is_industry: bool,
        window: int,
        trade_date: date | None,
        sort_by: str,
    ) -> list[TaxonomyStrengthSnapshot]:
        if trade_date is None:
            latest_stmt = (
                select(TaxonomyStrengthSnapshotModel.trade_date)
                .order_by(TaxonomyStrengthSnapshotModel.trade_date.desc())
                .limit(1)
            )
            trade_date = (await self.session.execute(latest_stmt)).scalar_one_or_none()
            if not trade_date:
                return []

        stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.window == window,
            TaxonomyStrengthSnapshotModel.trade_date == trade_date,
            TaxonomyStrengthSnapshotModel.algorithm_version == ALGORITHM_VERSION,
        )

        if is_industry:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.industry_id.is_not(None))
        else:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.theme_id.is_not(None))

        rows = list((await self.session.scalars(stmt)).all())
        snapshots = [await self._map_to_domain(r, is_industry) for r in rows]

        def sort_key(s: TaxonomyStrengthSnapshot):
            if sort_by == "return":
                val = s.equal_weight_return
            elif sort_by == "breadth":
                val = s.advance_ratio
            elif sort_by == "foreign_flow":
                val = s.foreign_net_amount
            elif sort_by == "turnover":
                val = (
                    s.turnover_amount
                    if s.turnover_amount is not None
                    else Decimal("-999999999999")
                )
            else:  # strength
                val = s.strength_score if s.strength_score is not None else Decimal("-9999")

            has_val = val is not None and val > Decimal("-999000000000")
            return (not has_val, -val if has_val else 0, s.taxonomy_code, str(s.taxonomy_id))

        snapshots.sort(key=sort_key)
        return snapshots

    async def get_taxonomy_strength_detail(
        self,
        taxonomy_id: UUID,
        is_industry: bool,
        window: int = 20,
        trade_date: date | None = None,
    ) -> TaxonomyStrengthDetail | None:
        stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.window == window,
            TaxonomyStrengthSnapshotModel.algorithm_version == ALGORITHM_VERSION,
        )
        if is_industry:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.industry_id == taxonomy_id)
        else:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.theme_id == taxonomy_id)

        if trade_date is not None:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.trade_date == trade_date)
        else:
            stmt = stmt.order_by(TaxonomyStrengthSnapshotModel.trade_date.desc())

        row = (await self.session.scalars(stmt)).first()
        if not row:
            return None

        snapshot = await self._map_to_domain(row, is_industry)
        leaders, laggards = await self._compute_leaders_and_laggards(
            taxonomy_id, is_industry, row.trade_date, window
        )

        return TaxonomyStrengthDetail(snapshot=snapshot, leaders=leaders, laggards=laggards)

    async def get_taxonomy_strength_history(
        self,
        taxonomy_id: UUID,
        is_industry: bool,
        window: int = 20,
        limit: int = 60,
    ) -> list[TaxonomyStrengthSnapshot]:
        stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.window == window,
            TaxonomyStrengthSnapshotModel.algorithm_version == ALGORITHM_VERSION,
        )
        if is_industry:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.industry_id == taxonomy_id)
        else:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.theme_id == taxonomy_id)

        stmt = stmt.order_by(TaxonomyStrengthSnapshotModel.trade_date.desc()).limit(limit)
        rows = list((await self.session.scalars(stmt)).all())
        rows.reverse()
        return [await self._map_to_domain(r, is_industry) for r in rows]

    async def _map_to_domain(
        self, r: TaxonomyStrengthSnapshotModel, is_industry: bool
    ) -> TaxonomyStrengthSnapshot:
        if is_industry:
            ind = await self.session.get(IndustryModel, r.industry_id)
            tax_id = ind.id if ind else r.industry_id
            tax_code = ind.code if ind else ""
            tax_name = ind.name if ind else ""
            tax_type = "OFFICIAL"
        else:
            th = await self.session.get(ThemeModel, r.theme_id)
            tax_id = th.id if th else r.theme_id
            tax_code = th.code if th else ""
            tax_name = th.name if th else ""
            tax_type = "CUSTOM"

        comps = StrengthComponents(
            momentum_score=r.momentum_score,
            breadth_score=r.breadth_score,
            technical_score=r.technical_score,
            institutional_score=r.institutional_score,
            turnover_score=r.turnover_score,
        )

        return TaxonomyStrengthSnapshot(
            id=r.id,
            taxonomy_id=tax_id,
            taxonomy_code=tax_code,
            taxonomy_name=tax_name,
            taxonomy_type=tax_type,
            trade_date=r.trade_date,
            window=r.window,
            equal_weight_return=r.equal_weight_return,
            market_cap_weighted_return=r.market_cap_weighted_return,
            total_members=r.total_members,
            valid_members=r.valid_members,
            coverage_ratio=r.coverage_ratio,
            advancers=r.advancers,
            decliners=r.decliners,
            unchanged=r.unchanged,
            advance_ratio=r.advance_ratio,
            above_ma20_pct=r.above_ma20_pct,
            above_ma60_pct=r.above_ma60_pct,
            foreign_net_amount=r.foreign_net_amount,
            investment_trust_net_amount=r.investment_trust_net_amount,
            dealer_net_amount=r.dealer_net_amount,
            margin_balance_change=r.margin_balance_change,
            short_balance_change=r.short_balance_change,
            lending_balance_change=r.lending_balance_change,
            turnover_amount=r.turnover_amount,
            turnover_share=r.turnover_share,
            turnover_momentum=r.turnover_momentum,
            components=comps,
            strength_score=r.strength_score,
            component_coverage=r.component_coverage,
            rank=r.rank,
            algorithm_version=r.algorithm_version,
            data_status=DataStatus(r.data_status),
            as_of=r.as_of,
        )

    async def _compute_leaders_and_laggards(
        self,
        taxonomy_id: UUID,
        is_industry: bool,
        trade_date: date,
        window: int,
    ) -> tuple[list[TaxonomyLeader], list[TaxonomyLeader]]:
        if is_industry:
            members_stmt = (
                select(SecurityModel)
                .join(SecurityIndustryModel, SecurityModel.id == SecurityIndustryModel.security_id)
                .where(SecurityIndustryModel.industry_id == taxonomy_id)
            )
        else:
            members_stmt = (
                select(SecurityModel)
                .join(SecurityThemeModel, SecurityModel.id == SecurityThemeModel.security_id)
                .where(SecurityThemeModel.theme_id == taxonomy_id)
            )

        securities = list((await self.session.scalars(members_stmt)).all())
        if not securities:
            return [], []

        sec_ids = [s.id for s in securities]

        days_stmt = (
            select(DailyPriceModel.trade_date)
            .where(DailyPriceModel.trade_date <= trade_date)
            .group_by(DailyPriceModel.trade_date)
            .order_by(DailyPriceModel.trade_date.desc())
            .limit(window + 1)
        )
        trading_days = list((await self.session.scalars(days_stmt)).all())
        if not trading_days:
            return [], []

        latest_date = trading_days[0]
        base_date = trading_days[-1]

        latest_prices = {
            p.security_id: p
            for p in (
                await self.session.scalars(
                    select(DailyPriceModel).where(
                        DailyPriceModel.security_id.in_(sec_ids),
                        DailyPriceModel.trade_date == latest_date,
                    )
                )
            ).all()
        }

        base_prices = {
            p.security_id: p
            for p in (
                await self.session.scalars(
                    select(DailyPriceModel).where(
                        DailyPriceModel.security_id.in_(sec_ids),
                        DailyPriceModel.trade_date == base_date,
                    )
                )
            ).all()
        }

        inst_flows = {
            f.security_id: f.foreign_investors_net
            for f in (
                await self.session.scalars(
                    select(InstitutionalSpotModel).where(
                        InstitutionalSpotModel.security_id.in_(sec_ids),
                        InstitutionalSpotModel.trade_date == latest_date,
                    )
                )
            ).all()
        }

        computed_members = []
        for sec in securities:
            lp = latest_prices.get(sec.id)
            bp = base_prices.get(sec.id)

            if lp and bp and bp.close and bp.close > 0 and lp.close:
                ret = ((lp.close / bp.close) - Decimal("1")) * Decimal("100")
                leader = TaxonomyLeader(
                    security_id=sec.id,
                    code=sec.code,
                    name=sec.name,
                    market=MarketCode(sec.market),
                    return_pct=ret.quantize(Decimal("0.01")),
                    foreign_net=(
                        Decimal(str(inst_flows.get(sec.id, 0)))
                        if sec.id in inst_flows
                        else None
                    ),
                    data_status=DataStatus.FINAL,
                )
                computed_members.append(leader)

        if not computed_members:
            return [], []

        computed_members.sort(key=lambda x: (-x.return_pct, x.code))

        leaders = computed_members[:5]
        laggards = sorted(computed_members[-5:], key=lambda x: (x.return_pct, x.code))

        return leaders, laggards
