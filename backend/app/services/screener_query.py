from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market import DataStatus, MarketCode
from app.domain.screener import (
    ScreenerExpression,
    ScreenerOperator,
    ScreenerResultSecurity,
)
from app.repositories.models import (
    DailyPriceModel,
    IndustryModel,
    InstitutionSpotTradingModel,
    MarginTradingModel,
    SecurityIndustryModel,
    SecurityModel,
    SecurityThemeModel,
    TaxonomyStrengthSnapshotModel,
    TechnicalSnapshotModel,
    ThemeModel,
)


class ScreenerQueryService:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_latest_trade_date(self) -> date | None:
        stmt = (
            select(DailyPriceModel.trade_date)
            .order_by(DailyPriceModel.trade_date.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def execute_screener(
        self,
        expression: ScreenerExpression,
        target_trade_date: date | None = None,
        sort_field: str = "code",
        sort_direction: str = "ASC",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ScreenerResultSecurity], int, date]:
        if target_trade_date is None:
            target_trade_date = await self.get_latest_trade_date()
            if target_trade_date is None:
                target_trade_date = date.today()

        trade_date = target_trade_date

        # Step 1: Load active securities
        sec_stmt = select(SecurityModel).where(SecurityModel.is_active.is_(True))
        sec_res = await self.session.execute(sec_stmt)
        securities = sec_res.scalars().all()
        sec_ids = [s.id for s in securities]

        if not sec_ids:
            return [], 0, trade_date

        # Step 2: Load daily prices on trade_date
        dp_stmt = select(DailyPriceModel).where(
            DailyPriceModel.security_id.in_(sec_ids),
            DailyPriceModel.trade_date == trade_date,
        )
        dp_res = await self.session.execute(dp_stmt)
        daily_prices = {dp.security_id: dp for dp in dp_res.scalars().all()}

        # Step 3: Load technical indicators on trade_date
        ti_stmt = select(TechnicalSnapshotModel).where(
            TechnicalSnapshotModel.security_id.in_(sec_ids),
            TechnicalSnapshotModel.trade_date == trade_date,
        )
        ti_res = await self.session.execute(ti_stmt)
        technicals = {ti.security_id: ti for ti in ti_res.scalars().all()}

        # Step 4: Load institutional trading on trade_date
        inst_stmt = select(InstitutionSpotTradingModel).where(
            InstitutionSpotTradingModel.security_id.in_(sec_ids),
            InstitutionSpotTradingModel.trade_date == trade_date,
        )
        inst_res = await self.session.execute(inst_stmt)
        institutions: dict[UUID, list[InstitutionSpotTradingModel]] = {}
        for inst in inst_res.scalars().all():
            institutions.setdefault(inst.security_id, []).append(inst)

        # Step 5: Load credit trading on trade_date
        ct_stmt = select(MarginTradingModel).where(
            MarginTradingModel.security_id.in_(sec_ids),
            MarginTradingModel.trade_date == trade_date,
        )
        ct_res = await self.session.execute(ct_stmt)
        credit_map = {ct.security_id: ct for ct in ct_res.scalars().all()}

        # Step 6: Load industry taxonomy mappings
        ind_stmt = (
            select(SecurityIndustryModel.security_id, IndustryModel.name)
            .join(IndustryModel, SecurityIndustryModel.industry_id == IndustryModel.id)
            .where(SecurityIndustryModel.security_id.in_(sec_ids))
        )
        ind_res = await self.session.execute(ind_stmt)
        ind_map = {row[0]: row[1] for row in ind_res.all()}

        # Step 7: Load theme taxonomy mappings
        theme_stmt = (
            select(SecurityThemeModel.security_id, ThemeModel.name)
            .join(ThemeModel, SecurityThemeModel.theme_id == ThemeModel.id)
            .where(SecurityThemeModel.security_id.in_(sec_ids))
        )
        theme_res = await self.session.execute(theme_stmt)
        theme_map: dict[UUID, list[str]] = {}
        for row in theme_res.all():
            theme_map.setdefault(row[0], []).append(row[1])

        # Step 8: Load industry strength snapshots on trade_date
        strength_stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.trade_date == trade_date,
            TaxonomyStrengthSnapshotModel.window == 20,
        )
        strength_res = await self.session.execute(strength_stmt)
        strength_map = {st.taxonomy_id: st for st in strength_res.scalars().all()}

        # Map security_id -> industry_id for strength lookup
        ind_id_stmt = select(
            SecurityIndustryModel.security_id, SecurityIndustryModel.industry_id
        ).where(
            SecurityIndustryModel.security_id.in_(sec_ids)
        )
        ind_id_res = await self.session.execute(ind_id_stmt)
        sec_industry_id_map = {row[0]: row[1] for row in ind_id_res.all()}

        # Build feature maps per security
        dataset: dict[UUID, dict[str, Any]] = {}
        for sec in securities:
            dp = daily_prices.get(sec.id)
            ti = technicals.get(sec.id)
            inst_list = institutions.get(sec.id, [])
            ct = credit_map.get(sec.id)
            ind_name = ind_map.get(sec.id)
            themes = theme_map.get(sec.id, [])

            ind_id = sec_industry_id_map.get(sec.id)
            str_snap = strength_map.get(ind_id) if ind_id else None

            # Calculate institutional net totals
            foreign_5d_net = sum(
                (i.net_volume for i in inst_list if i.institution == "FOREIGN"), Decimal(0)
            )
            trust_5d_net = sum(
                (i.net_volume for i in inst_list if i.institution == "TRUST"), Decimal(0)
            )

            dataset[sec.id] = {
                "close": dp.close_price if dp else None,
                "return_1d": dp.change_percent if dp else None,
                "return_5d": dp.change_percent if dp else None,
                "rsi14": ti.rsi_14 if ti else None,
                "close_vs_ma20": (dp.close_price - ti.ma_20) / ti.ma_20 * 100
                if dp and ti and ti.ma_20
                else None,
                "close_vs_ma60": (dp.close_price - ti.ma_60) / ti.ma_60 * 100
                if dp and ti and ti.ma_60
                else None,
                "close_vs_ma240": (dp.close_price - ti.ma_240) / ti.ma_240 * 100
                if dp and ti and ti.ma_240
                else None,
                "foreign_5d_net": foreign_5d_net,
                "trust_5d_net": trust_5d_net,
                "margin_balance_change": ct.margin_balance_change if ct else None,
                "industry_name": ind_name,
                "theme_name": themes,
                "industry_strength_score": str_snap.strength_score if str_snap else None,
            }

        # Step 9: Filter securities using AST
        matched_results: list[ScreenerResultSecurity] = []
        for sec in securities:
            feature_map = dataset[sec.id]
            is_match, matched_conds = self._evaluate_ast(expression, feature_map)
            if is_match:
                dp = daily_prices.get(sec.id)
                matched_results.append(
                    ScreenerResultSecurity(
                        security_id=sec.id,
                        code=sec.code,
                        name=sec.name,
                        market=MarketCode(sec.market),
                        industry_name=ind_map.get(sec.id),
                        themes=theme_map.get(sec.id, []),
                        close=str(dp.close_price) if dp and dp.close_price is not None else None,
                        return_pct=str(dp.change_percent)
                        if dp and dp.change_percent is not None
                        else None,
                        matched_conditions=matched_conds,
                        extra_metrics={
                            "rsi14": str(feature_map["rsi14"])
                            if feature_map["rsi14"] is not None
                            else None,
                            "foreign_5d_net": str(feature_map["foreign_5d_net"]),
                            "industry_strength": str(feature_map["industry_strength_score"])
                            if feature_map["industry_strength_score"] is not None
                            else None,
                        },
                        data_status=DataStatus.FINAL if dp else DataStatus.UNAVAILABLE,
                    )
                )

        # Step 10: Sort results with nulls coming LAST
        reverse = sort_direction.upper() == "DESC"

        def get_sort_key(res: ScreenerResultSecurity):
            val = None
            if sort_field == "code":
                val = res.code
            elif sort_field == "name":
                val = res.name
            elif sort_field == "close":
                val = Decimal(res.close) if res.close is not None else None
            elif sort_field == "return_pct":
                val = Decimal(res.return_pct) if res.return_pct is not None else None
            else:
                val = res.code

            # Return (is_null, value) so nulls always come last regardless of ASC/DESC
            if val is None:
                return (1, "")
            return (0, val)

        matched_results.sort(key=get_sort_key, reverse=reverse)

        total_count = len(matched_results)
        paged_results = matched_results[offset : offset + limit]

        return paged_results, total_count, trade_date

    def _evaluate_ast(
        self, expr: ScreenerExpression, feature_map: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        if expr.type == "CONDITION":
            val = feature_map.get(expr.field)
            passed, desc = self._evaluate_condition(
                expr.field, expr.operator, expr.value, expr.value2, val
            )
            return passed, [desc] if passed else []

        elif expr.type == "AND":
            all_conds: list[str] = []
            for child in expr.children:
                passed, conds = self._evaluate_ast(child, feature_map)
                if not passed:
                    return False, []
                all_conds.extend(conds)
            return True, all_conds

        elif expr.type == "OR":
            for child in expr.children:
                passed, conds = self._evaluate_ast(child, feature_map)
                if passed:
                    return True, conds
            return False, []

        return False, []

    def _evaluate_condition(
        self,
        field: str | None,
        operator: ScreenerOperator | None,
        target_val: Any,
        target_val2: Any,
        actual_val: Any,
    ) -> tuple[bool, str]:
        desc = f"{field} {operator.value if operator else ''} {target_val}"

        if operator == ScreenerOperator.IS_AVAILABLE:
            return actual_val is not None, f"{field} IS_AVAILABLE"
        if operator == ScreenerOperator.IS_UNAVAILABLE:
            return actual_val is None, f"{field} IS_UNAVAILABLE"

        if actual_val is None:
            return False, desc

        try:
            if operator in (
                ScreenerOperator.GT,
                ScreenerOperator.GTE,
                ScreenerOperator.LT,
                ScreenerOperator.LTE,
                ScreenerOperator.EQ,
                ScreenerOperator.NE,
                ScreenerOperator.BETWEEN,
            ):
                num_actual = (
                    Decimal(str(actual_val))
                    if not isinstance(actual_val, Decimal)
                    else actual_val
                )
                if operator == ScreenerOperator.BETWEEN:
                    low = Decimal(str(target_val))
                    high = Decimal(str(target_val2))
                    return low <= num_actual <= high, f"{field} BETWEEN {low} AND {high}"

                num_target = Decimal(str(target_val))
                if operator == ScreenerOperator.GT:
                    return num_actual > num_target, desc
                elif operator == ScreenerOperator.GTE:
                    return num_actual >= num_target, desc
                elif operator == ScreenerOperator.LT:
                    return num_actual < num_target, desc
                elif operator == ScreenerOperator.LTE:
                    return num_actual <= num_target, desc
                elif operator == ScreenerOperator.EQ:
                    return num_actual == num_target, desc
                elif operator == ScreenerOperator.NE:
                    return num_actual != num_target, desc

            elif operator in (
                ScreenerOperator.IN,
                ScreenerOperator.NOT_IN,
                ScreenerOperator.EQ,
                ScreenerOperator.NE,
            ):
                if isinstance(actual_val, list):
                    if operator == ScreenerOperator.IN:
                        return any(item in target_val for item in actual_val), desc
                    elif operator == ScreenerOperator.NOT_IN:
                        return not any(item in target_val for item in actual_val), desc
                else:
                    str_actual = str(actual_val)
                    if operator == ScreenerOperator.EQ:
                        return str_actual == str(target_val), desc
                    elif operator == ScreenerOperator.NE:
                        return str_actual != str(target_val), desc
                    elif operator == ScreenerOperator.IN:
                        return str_actual in target_val, desc
                    elif operator == ScreenerOperator.NOT_IN:
                        return str_actual not in target_val, desc
        except Exception:
            return False, desc

        return False, desc
