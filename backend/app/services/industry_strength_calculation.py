from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.market_data import DataStatus
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
from app.services.industry_strength_scoring import IndustryStrengthScoringService


class IndustryStrengthCalculationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.scoring_service = IndustryStrengthScoringService()

    def get_trading_days(self, target_date: date, count: int) -> list[date]:
        """Get 'count' distinct trading dates up to target_date in descending order."""
        stmt = (
            select(DailyPriceModel.trade_date)
            .where(DailyPriceModel.trade_date <= target_date)
            .group_by(DailyPriceModel.trade_date)
            .order_by(DailyPriceModel.trade_date.desc())
            .limit(count)
        )
        return list(self.session.scalars(stmt).all())

    def calculate_for_date(
        self, target_date: date, windows: list[int] | None = None
    ) -> dict[str, int]:
        """Calculate and persist taxonomy strength snapshots for a given date across all windows."""
        if windows is None:
            windows = [1, 5, 10, 20, 60]

        # Fetch all official industries
        industries = list(self.session.scalars(select(IndustryModel)).all())
        # Fetch all custom themes
        themes = list(self.session.scalars(select(ThemeModel)).all())

        inserted_count = 0
        updated_count = 0

        for window in windows:
            trading_days = self.get_trading_days(target_date, window + 1)
            if not trading_days:
                continue

            latest_date = trading_days[0]
            base_date = trading_days[-1] if len(trading_days) > window else trading_days[-1]

            # Calculate raw metrics for official industries
            ind_raw_list = []
            for ind in industries:
                members_stmt = (
                    select(SecurityModel.id, SecurityModel.code)
                    .join(
                        SecurityIndustryModel,
                        SecurityModel.id == SecurityIndustryModel.security_id,
                    )
                    .where(SecurityIndustryModel.industry_id == ind.id)
                )
                member_rows = self.session.execute(members_stmt).all()
                if not member_rows:
                    continue

                sec_ids = [r[0] for r in member_rows]
                sec_codes = {r[0]: r[1] for r in member_rows}

                raw_metric = self._aggregate_taxonomy_metrics(
                    taxonomy_id=ind.id,
                    taxonomy_code=ind.code,
                    taxonomy_name=ind.name,
                    taxonomy_type="OFFICIAL",
                    sec_ids=sec_ids,
                    sec_codes=sec_codes,
                    latest_date=latest_date,
                    base_date=base_date,
                    window=window,
                    trading_days=trading_days[:window],
                )
                ind_raw_list.append(raw_metric)

            # Score official industries
            scored_industries = self.scoring_service.score_group(ind_raw_list)

            # Save official industry snapshots
            for item in scored_industries:
                ins, upd = self._upsert_snapshot(item, is_industry=True)
                inserted_count += ins
                updated_count += upd

            # Calculate raw metrics for themes
            theme_raw_list = []
            for th in themes:
                members_stmt = (
                    select(SecurityModel.id, SecurityModel.code)
                    .join(SecurityThemeModel, SecurityModel.id == SecurityThemeModel.security_id)
                    .where(SecurityThemeModel.theme_id == th.id)
                )
                member_rows = self.session.execute(members_stmt).all()
                if not member_rows:
                    continue

                sec_ids = [r[0] for r in member_rows]
                sec_codes = {r[0]: r[1] for r in member_rows}

                raw_metric = self._aggregate_taxonomy_metrics(
                    taxonomy_id=th.id,
                    taxonomy_code=th.code,
                    taxonomy_name=th.name,
                    taxonomy_type="CUSTOM",
                    sec_ids=sec_ids,
                    sec_codes=sec_codes,
                    latest_date=latest_date,
                    base_date=base_date,
                    window=window,
                    trading_days=trading_days[:window],
                )
                theme_raw_list.append(raw_metric)

            # Score custom themes
            scored_themes = self.scoring_service.score_group(theme_raw_list)

            # Save theme snapshots
            for item in scored_themes:
                ins, upd = self._upsert_snapshot(item, is_industry=False)
                inserted_count += ins
                updated_count += upd

        self.session.commit()
        return {"inserted": inserted_count, "updated": updated_count}

    def _aggregate_taxonomy_metrics(
        self,
        taxonomy_id: UUID,
        taxonomy_code: str,
        taxonomy_name: str,
        taxonomy_type: str,
        sec_ids: list[UUID],
        sec_codes: dict[UUID, str],
        latest_date: date,
        base_date: date,
        window: int,
        trading_days: list[date],
    ) -> dict:
        total_members = len(sec_ids)

        # 1. Price Return & Breadth
        latest_prices = {
            p.security_id: p
            for p in self.session.scalars(
                select(DailyPriceModel).where(
                    DailyPriceModel.security_id.in_(sec_ids),
                    DailyPriceModel.trade_date == latest_date,
                )
            )
        }

        base_prices = {
            p.security_id: p
            for p in self.session.scalars(
                select(DailyPriceModel).where(
                    DailyPriceModel.security_id.in_(sec_ids),
                    DailyPriceModel.trade_date == base_date,
                )
            )
        }

        valid_returns = []
        advancers = 0
        decliners = 0
        unchanged = 0
        total_turnover = Decimal("0")
        has_turnover = False

        for sec_id in sec_ids:
            lp = latest_prices.get(sec_id)
            bp = base_prices.get(sec_id)

            if lp and lp.volume is not None:
                # Accumulate volume as turnover estimation
                # if explicit turnover_amount not in daily_prices
                total_turnover += Decimal(str(lp.close * lp.volume))
                has_turnover = True

            if lp and bp and bp.close and bp.close > 0 and lp.close:
                ret = (lp.close / bp.close) - Decimal("1")
                valid_returns.append((sec_id, ret, lp.close))

                if window == 1:
                    if lp.change and lp.change > 0:
                        advancers += 1
                    elif lp.change and lp.change < 0:
                        decliners += 1
                    else:
                        unchanged += 1
                else:
                    if ret > 0:
                        advancers += 1
                    elif ret < 0:
                        decliners += 1
                    else:
                        unchanged += 1

        valid_members = len(valid_returns)
        if valid_members > 0:
            eq_return = (sum(r[1] for r in valid_returns) / Decimal(str(valid_members))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            coverage_ratio = (Decimal(str(valid_members)) / Decimal(str(total_members))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            advance_ratio = (Decimal(str(advancers)) / Decimal(str(valid_members))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        else:
            eq_return = Decimal("0")
            coverage_ratio = Decimal("0")
            advance_ratio = Decimal("0")

        # 2. Technical MA Participation
        tech_snapshots = list(
            self.session.scalars(
                select(TechnicalSnapshotModel).where(
                    TechnicalSnapshotModel.security_id.in_(sec_ids),
                    TechnicalSnapshotModel.trade_date == latest_date,
                )
            )
        )
        ma20_above = 0
        ma20_valid = 0
        ma60_above = 0
        ma60_valid = 0

        for ts in tech_snapshots:
            lp = latest_prices.get(ts.security_id)
            if lp and lp.close and ts.ma20:
                ma20_valid += 1
                if lp.close >= ts.ma20:
                    ma20_above += 1
            if lp and lp.close and ts.ma60:
                ma60_valid += 1
                if lp.close >= ts.ma60:
                    ma60_above += 1

        above_ma20_pct = (
            (Decimal(str(ma20_above)) / Decimal(str(ma20_valid))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            if ma20_valid > 0
            else Decimal("0")
        )
        above_ma60_pct = (
            (Decimal(str(ma60_above)) / Decimal(str(ma60_valid))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            if ma60_valid > 0
            else Decimal("0")
        )

        # 3. Institutional Flow
        inst_rows = list(
            self.session.scalars(
                select(InstitutionSpotTradingModel).where(
                    InstitutionSpotTradingModel.security_id.in_(sec_ids),
                    InstitutionSpotTradingModel.trade_date.in_(trading_days),
                )
            )
        )
        foreign_net = Decimal("0")
        trust_net = Decimal("0")
        dealer_net = Decimal("0")

        for r in inst_rows:
            val = (
                Decimal(str(r.net_amount))
                if r.net_amount is not None
                else (Decimal(str(r.net_shares)) if r.net_shares is not None else Decimal("0"))
            )
            if r.institution_type == "FOREIGN":
                foreign_net += val
            elif r.institution_type == "INVESTMENT_TRUST":
                trust_net += val
            elif r.institution_type == "DEALER":
                dealer_net += val

        # 4. Credit Changes
        credit_rows = list(
            self.session.scalars(
                select(MarginTradingModel).where(
                    MarginTradingModel.security_id.in_(sec_ids),
                    MarginTradingModel.trade_date.in_(trading_days),
                )
            )
        )
        margin_change = Decimal(str(sum((r.margin_balance_change or 0) for r in credit_rows)))
        short_change = Decimal(str(sum((r.short_balance_change or 0) for r in credit_rows)))

        status = DataStatus.FINAL.value if valid_members > 0 else DataStatus.PARTIAL.value
        return {
            "taxonomy_id": taxonomy_id,
            "taxonomy_code": taxonomy_code,
            "taxonomy_name": taxonomy_name,
            "taxonomy_type": taxonomy_type,
            "trade_date": latest_date,
            "window": window,
            "equal_weight_return": eq_return,
            "market_cap_weighted_return": None,  # UNAVAILABLE per spec
            "total_members": total_members,
            "valid_members": valid_members,
            "coverage_ratio": coverage_ratio,
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": unchanged,
            "advance_ratio": advance_ratio,
            "above_ma20_pct": above_ma20_pct,
            "above_ma60_pct": above_ma60_pct,
            "foreign_net_amount": foreign_net,
            "investment_trust_net_amount": trust_net,
            "dealer_net_amount": dealer_net,
            "margin_balance_change": margin_change,
            "short_balance_change": short_change,
            "lending_balance_change": None,  # UNAVAILABLE per spec
            "turnover_amount": total_turnover if has_turnover else None,
            "turnover_share": None,
            "turnover_momentum": Decimal("1.0") if has_turnover else None,
            "data_status": status,
            "as_of": datetime.now(UTC),
        }

    def _upsert_snapshot(self, item: dict, is_industry: bool) -> tuple[int, int]:
        ind_id = item["taxonomy_id"] if is_industry else None
        theme_id = item["taxonomy_id"] if not is_industry else None

        stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.trade_date == item["trade_date"],
            TaxonomyStrengthSnapshotModel.window == item["window"],
            TaxonomyStrengthSnapshotModel.algorithm_version == item["algorithm_version"],
        )
        if is_industry:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.industry_id == ind_id)
        else:
            stmt = stmt.where(TaxonomyStrengthSnapshotModel.theme_id == theme_id)

        existing = self.session.scalars(stmt).first()

        comps = item["components"]

        if existing:
            existing.equal_weight_return = item["equal_weight_return"]
            existing.market_cap_weighted_return = item["market_cap_weighted_return"]
            existing.total_members = item["total_members"]
            existing.valid_members = item["valid_members"]
            existing.coverage_ratio = item["coverage_ratio"]
            existing.advancers = item["advancers"]
            existing.decliners = item["decliners"]
            existing.unchanged = item["unchanged"]
            existing.advance_ratio = item["advance_ratio"]
            existing.above_ma20_pct = item["above_ma20_pct"]
            existing.above_ma60_pct = item["above_ma60_pct"]
            existing.foreign_net_amount = item["foreign_net_amount"]
            existing.investment_trust_net_amount = item["investment_trust_net_amount"]
            existing.dealer_net_amount = item["dealer_net_amount"]
            existing.margin_balance_change = item["margin_balance_change"]
            existing.short_balance_change = item["short_balance_change"]
            existing.lending_balance_change = item["lending_balance_change"]
            existing.turnover_amount = item["turnover_amount"]
            existing.turnover_share = item["turnover_share"]
            existing.turnover_momentum = item["turnover_momentum"]
            existing.momentum_score = comps.momentum_score
            existing.breadth_score = comps.breadth_score
            existing.technical_score = comps.technical_score
            existing.institutional_score = comps.institutional_score
            existing.turnover_score = comps.turnover_score
            existing.strength_score = item["strength_score"]
            existing.component_coverage = item["component_coverage"]
            existing.rank = item["rank"]
            existing.data_status = item["data_status"]
            existing.as_of = item["as_of"]
            return 0, 1
        else:
            snapshot = TaxonomyStrengthSnapshotModel(
                industry_id=ind_id,
                theme_id=theme_id,
                trade_date=item["trade_date"],
                window=item["window"],
                equal_weight_return=item["equal_weight_return"],
                market_cap_weighted_return=item["market_cap_weighted_return"],
                total_members=item["total_members"],
                valid_members=item["valid_members"],
                coverage_ratio=item["coverage_ratio"],
                advancers=item["advancers"],
                decliners=item["decliners"],
                unchanged=item["unchanged"],
                advance_ratio=item["advance_ratio"],
                above_ma20_pct=item["above_ma20_pct"],
                above_ma60_pct=item["above_ma60_pct"],
                foreign_net_amount=item["foreign_net_amount"],
                investment_trust_net_amount=item["investment_trust_net_amount"],
                dealer_net_amount=item["dealer_net_amount"],
                margin_balance_change=item["margin_balance_change"],
                short_balance_change=item["short_balance_change"],
                lending_balance_change=item["lending_balance_change"],
                turnover_amount=item["turnover_amount"],
                turnover_share=item["turnover_share"],
                turnover_momentum=item["turnover_momentum"],
                momentum_score=comps.momentum_score,
                breadth_score=comps.breadth_score,
                technical_score=comps.technical_score,
                institutional_score=comps.institutional_score,
                turnover_score=comps.turnover_score,
                strength_score=item["strength_score"],
                component_coverage=item["component_coverage"],
                rank=item["rank"],
                algorithm_version=item["algorithm_version"],
                data_status=item["data_status"],
                as_of=item["as_of"],
            )
            self.session.add(snapshot)
            return 1, 0
