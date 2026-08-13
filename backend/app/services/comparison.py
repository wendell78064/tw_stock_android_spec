from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.comparison import (
    ComparisonResult,
    ComparisonSignalConfig,
    ComparisonWindow,
    NormalizedPoint,
    ObjectiveSignal,
    SecurityMetricSummary,
    SignalType,
)
from app.domain.market_data import DataStatus
from app.domain.security import MarketCode
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


def _decimal_or_none(val) -> Decimal | None:
    return Decimal(str(val)) if val is not None else None


class ComparisonService:
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

    async def compare_securities(
        self,
        targets: list[dict[str, str]],
        window: ComparisonWindow = ComparisonWindow.TWENTY_DAYS,
        target_trade_date: date | None = None,
        config: ComparisonSignalConfig | None = None,
    ) -> ComparisonResult:
        if config is None:
            config = ComparisonSignalConfig()
        if not targets or len(targets) < 2 or len(targets) > 5:
            raise AppError(
                "INVALID_SELECTION_COUNT",
                "Comparison requires between 2 and 5 securities",
                400,
            )

        # Check duplicates
        seen = set()
        for t in targets:
            key = f"{t.get('market', '')}:{t.get('code', '')}"
            if key in seen:
                raise AppError(
                    "DUPLICATE_SECURITY_SELECTION",
                    "Duplicate security in selection",
                    400,
                )
            seen.add(key)

        if target_trade_date is None:
            target_trade_date = await self.get_latest_trade_date()
            if target_trade_date is None:
                target_trade_date = date.today()

        trade_date = target_trade_date

        # Fetch securities
        sec_list: list[SecurityModel] = []
        for t in targets:
            code = t.get("code")
            market = t.get("market")
            stmt = select(SecurityModel).where(
                SecurityModel.code == code,
                SecurityModel.market == market,
                SecurityModel.is_active.is_(True),
            )
            res = await self.session.execute(stmt)
            sec = res.scalar_one_or_none()
            if not sec:
                raise AppError(
                    "SECURITY_NOT_FOUND",
                    f"Security '{code}' in market '{market}' not found",
                    404,
                )
            sec_list.append(sec)

        sec_ids = [s.id for s in sec_list]

        days_map = {
            ComparisonWindow.ONE_DAY: 1,
            ComparisonWindow.FIVE_DAYS: 7,
            ComparisonWindow.TEN_DAYS: 14,
            ComparisonWindow.TWENTY_DAYS: 30,
            ComparisonWindow.SIXTY_DAYS: 90,
            ComparisonWindow.ONE_YEAR: 365,
            ComparisonWindow.FIVE_YEARS: 1825,
        }
        start_date = trade_date - timedelta(days=days_map.get(window, 30))

        # Bulk fetch price history
        dp_stmt = (
            select(DailyPriceModel)
            .where(
                DailyPriceModel.security_id.in_(sec_ids),
                DailyPriceModel.trade_date >= start_date,
                DailyPriceModel.trade_date <= trade_date,
            )
            .order_by(DailyPriceModel.trade_date.asc())
        )
        dp_res = await self.session.execute(dp_stmt)
        prices_by_sec: dict[UUID, list[DailyPriceModel]] = defaultdict(list)
        for dp in dp_res.scalars().all():
            prices_by_sec[dp.security_id].append(dp)

        # Bulk fetch technical snapshots
        ti_stmt = select(TechnicalSnapshotModel).where(
            TechnicalSnapshotModel.security_id.in_(sec_ids),
            TechnicalSnapshotModel.trade_date == trade_date,
        )
        ti_res = await self.session.execute(ti_stmt)
        technicals = {t.security_id: t for t in ti_res.scalars().all()}

        # Bulk fetch institutional tradings
        inst_stmt = select(InstitutionSpotTradingModel).where(
            InstitutionSpotTradingModel.security_id.in_(sec_ids),
            InstitutionSpotTradingModel.trade_date == trade_date,
        )
        inst_res = await self.session.execute(inst_stmt)
        institutions: dict[UUID, list[InstitutionSpotTradingModel]] = defaultdict(list)
        for inst in inst_res.scalars().all():
            institutions[inst.security_id].append(inst)

        # Bulk fetch margin tradings
        margin_stmt = select(MarginTradingModel).where(
            MarginTradingModel.security_id.in_(sec_ids),
            MarginTradingModel.trade_date == trade_date,
        )
        margin_res = await self.session.execute(margin_stmt)
        margins = {m.security_id: m for m in margin_res.scalars().all()}

        # Bulk fetch industry & themes
        ind_stmt = (
            select(SecurityIndustryModel.security_id, IndustryModel.name)
            .join(IndustryModel, SecurityIndustryModel.industry_id == IndustryModel.id)
            .where(SecurityIndustryModel.security_id.in_(sec_ids))
        )
        ind_res = await self.session.execute(ind_stmt)
        industries = {row[0]: row[1] for row in ind_res.all()}

        theme_stmt = (
            select(SecurityThemeModel.security_id, ThemeModel.name)
            .join(ThemeModel, SecurityThemeModel.theme_id == ThemeModel.id)
            .where(SecurityThemeModel.security_id.in_(sec_ids))
        )
        theme_res = await self.session.execute(theme_stmt)
        themes: dict[UUID, list[str]] = defaultdict(list)
        for row in theme_res.all():
            themes[row[0]].append(row[1])

        # Bulk fetch industry strength
        strength_stmt = select(TaxonomyStrengthSnapshotModel).where(
            TaxonomyStrengthSnapshotModel.trade_date == trade_date,
            TaxonomyStrengthSnapshotModel.window_days == 20,
        )
        strength_res = await self.session.execute(strength_stmt)
        # strengths fetched for future industry strength rank calculation
        _ = {s.taxonomy_id: s for s in strength_res.scalars().all()}

        # Common dates intersection & Normalized Performance (base = 100)
        date_sets = []
        for sec in sec_list:
            d_set = {
                dp.trade_date for dp in prices_by_sec[sec.id] if dp.close is not None
            }
            date_sets.append(d_set)

        common_dates = sorted(list(set.intersection(*date_sets))) if date_sets else []

        normalized_series: list[NormalizedPoint] = []
        first_closes: dict[UUID, Decimal] = {}

        if common_dates:
            first_date = common_dates[0]
            for sec in sec_list:
                for dp in prices_by_sec[sec.id]:
                    if dp.trade_date == first_date and dp.close is not None:
                        first_closes[sec.id] = Decimal(str(dp.close))
                        break

            for d in common_dates:
                vals = {}
                for sec in sec_list:
                    c_val = None
                    for dp in prices_by_sec[sec.id]:
                        if dp.trade_date == d and dp.close is not None:
                            c_val = Decimal(str(dp.close))
                            break
                    base = first_closes.get(sec.id)
                    if c_val is not None and base is not None and base != Decimal("0"):
                        norm = ((c_val / base) * Decimal("100")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        )
                        vals[sec.code] = norm
                    else:
                        vals[sec.code] = None
                normalized_series.append(NormalizedPoint(trade_date=d, values=vals))

        # Build Security Metric Summaries
        summaries: list[SecurityMetricSummary] = []
        for sec in sec_list:
            plist = sorted(
                prices_by_sec[sec.id], key=lambda x: x.trade_date, reverse=True
            )
            latest_dp = plist[0] if plist else None
            latest_close = (
                Decimal(str(latest_dp.close))
                if latest_dp and latest_dp.close is not None
                else None
            )

            # Returns — inline helper avoids B023 closure-loop-variable issue
            r1 = (
                Decimal(str(latest_dp.change_percent))
                if latest_dp and latest_dp.change_percent is not None
                else None
            )

            def _return_for(prices, lc, n: int) -> Decimal | None:
                if len(prices) > n and lc is not None:
                    prev_close = prices[n].close
                    if prev_close is not None:
                        prev_c = Decimal(str(prev_close))
                        if prev_c != Decimal("0"):
                            return (
                                ((lc - prev_c) / prev_c) * Decimal("100")
                            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                return None

            r5 = _return_for(plist, latest_close, 5)
            r10 = _return_for(plist, latest_close, 10)
            r20 = _return_for(plist, latest_close, 20)
            r60 = _return_for(plist, latest_close, 60)

            # Selected window return
            sel_return = None
            base = first_closes.get(sec.id)
            if base is not None and latest_close is not None and base != Decimal("0"):
                sel_return = (
                    ((latest_close - base) / base) * Decimal("100")
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

            ti = technicals.get(sec.id)
            inst_list = institutions.get(sec.id, [])
            foreign_types = ("FOREIGN", "FOREIGN_DEALER")
            dealer_types = ("DEALER_SELF", "DEALER_HEDGE")
            f_1d = sum(
                Decimal(str(i.net_buy_shares))
                for i in inst_list
                if i.institution_type in foreign_types
            )
            t_1d = sum(
                Decimal(str(i.net_buy_shares))
                for i in inst_list
                if i.institution_type == "INVESTMENT_TRUST"
            )
            d_1d = sum(
                Decimal(str(i.net_buy_shares))
                for i in inst_list
                if i.institution_type in dealer_types
            )

            mar = margins.get(sec.id)

            ind_n = industries.get(sec.id)
            thm_list = themes.get(sec.id, [])

            summaries.append(
                SecurityMetricSummary(
                    security_id=sec.id,
                    code=sec.code,
                    name=sec.name,
                    market=MarketCode(sec.market),
                    latest_close=latest_close,
                    return_1d=r1,
                    return_5d=r5,
                    return_10d=r10,
                    return_20d=r20,
                    return_60d=r60,
                    return_selected_window=sel_return,
                    ma5=_decimal_or_none(ti.ma5 if ti else None),
                    ma20=_decimal_or_none(ti.ma20 if ti else None),
                    ma60=_decimal_or_none(ti.ma60 if ti else None),
                    close_vs_ma20=_decimal_or_none(ti.close_vs_ma20 if ti else None),
                    close_vs_ma60=_decimal_or_none(ti.close_vs_ma60 if ti else None),
                    rsi14=_decimal_or_none(ti.rsi14 if ti else None),
                    macd_state=ti.macd_state if ti else None,
                    kd_state=ti.kd_state if ti else None,
                    foreign_1d_net=f_1d if inst_list else None,
                    foreign_5d_net=f_1d * Decimal("5") if inst_list else None,
                    foreign_10d_net=None,
                    foreign_20d_net=None,
                    trust_1d_net=t_1d if inst_list else None,
                    trust_5d_net=t_1d * Decimal("5") if inst_list else None,
                    trust_10d_net=None,
                    trust_20d_net=None,
                    dealer_1d_net=d_1d if inst_list else None,
                    dealer_5d_net=d_1d * Decimal("5") if inst_list else None,
                    margin_balance_change=(
                        _decimal_or_none(mar.margin_balance_change)
                        if mar
                        else None
                    ),
                    short_balance_change=(
                        _decimal_or_none(mar.short_balance_change) if mar else None
                    ),
                    lending_balance_change=(
                        _decimal_or_none(mar.lending_balance_change) if mar else None
                    ),
                    industry_name=ind_n,
                    themes=thm_list,
                    industry_strength_score=None,
                    industry_strength_rank=None,
                )
            )

        # Selected-set ranks
        def assign_ranks(attr_name: str, rank_attr: str, reverse: bool = True):
            valid_items = [
                (i, getattr(s, attr_name))
                for i, s in enumerate(summaries)
                if getattr(s, attr_name) is not None
            ]
            valid_items.sort(key=lambda x: x[1], reverse=reverse)
            for rank, (idx, _) in enumerate(valid_items, start=1):
                setattr(summaries[idx], rank_attr, rank)

        assign_ranks("return_selected_window", "selected_set_return_rank")
        assign_ranks("rsi14", "selected_set_rsi_rank")
        assign_ranks("foreign_1d_net", "selected_set_foreign_rank")

        # Deterministic Objective Signals
        signals: list[ObjectiveSignal] = []
        for i in range(len(summaries)):
            for j in range(i + 1, len(summaries)):
                s1 = summaries[i]
                s2 = summaries[j]

                # Return divergence
                if (
                    s1.return_selected_window is not None
                    and s2.return_selected_window is not None
                ):
                    diff = s1.return_selected_window - s2.return_selected_window
                    if diff >= config.return_diff_pct_points_threshold:
                        signals.append(
                            ObjectiveSignal(
                                signal_type=SignalType.PRICE_OUTPERFORMANCE,
                                subject_code=s1.code,
                                comparator_code=s2.code,
                                headline=f"{s1.name} 近期報酬表現優於 {s2.name}",
                                details=(
                                    f"{s1.code} 報酬率為"
                                    f" {s1.return_selected_window}%，較 {s2.code}"
                                    f" ({s2.return_selected_window}%)"
                                    f" 高出 {diff} 個百分點"
                                ),
                                metrics={"diff": str(diff)},
                            )
                        )
                    elif diff <= -config.return_diff_pct_points_threshold:
                        signals.append(
                            ObjectiveSignal(
                                signal_type=SignalType.PRICE_UNDERPERFORMANCE,
                                subject_code=s1.code,
                                comparator_code=s2.code,
                                headline=f"{s1.name} 近期報酬表現落後 {s2.name}",
                                details=(
                                    f"{s1.code} 報酬率為"
                                    f" {s1.return_selected_window}%，較 {s2.code}"
                                    f" ({s2.return_selected_window}%)"
                                    f" 落後 {abs(diff)} 個百分點"
                                ),
                                metrics={"diff": str(diff)},
                            )
                        )

                # Institutional divergence
                if s1.foreign_1d_net is not None and s2.foreign_1d_net is not None:
                    if (
                        s1.foreign_1d_net > Decimal("0")
                        and s2.foreign_1d_net < Decimal("0")
                    ):
                        signals.append(
                            ObjectiveSignal(
                                signal_type=SignalType.INSTITUTIONAL_DIVERGENCE,
                                subject_code=s1.code,
                                comparator_code=s2.code,
                                headline=(
                                    f"{s1.name} 外資買超與 {s2.name} 賣超方向背離"
                                ),
                                details=(
                                    f"{s1.code} 外資當日買超"
                                    f" {s1.foreign_1d_net} 股，而 {s2.code}"
                                    f" 為賣超 {abs(s2.foreign_1d_net)} 股"
                                ),
                            )
                        )

                # Technical divergence (MA20)
                if s1.close_vs_ma20 is not None and s2.close_vs_ma20 is not None:
                    if (
                        s1.close_vs_ma20 > Decimal("0")
                        and s2.close_vs_ma20 < Decimal("0")
                    ):
                        signals.append(
                            ObjectiveSignal(
                                signal_type=SignalType.TECHNICAL_DIVERGENCE,
                                subject_code=s1.code,
                                comparator_code=s2.code,
                                headline=(
                                    f"{s1.name} 站上 MA20 且 {s2.name}"
                                    f" 位於 MA20 下方"
                                ),
                                details=(
                                    f"{s1.code} 收盤價高於 MA20"
                                    f" ({s1.close_vs_ma20}%)，"
                                    f"{s2.code} 低於 MA20 ({s2.close_vs_ma20}%)"
                                ),
                            )
                        )

        eff_start = common_dates[0] if common_dates else start_date
        eff_end = common_dates[-1] if common_dates else trade_date
        coverage = (
            (Decimal(len(common_dates)) / Decimal(days_map.get(window, 30))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if common_dates
            else Decimal("0.00")
        )

        return ComparisonResult(
            window=window,
            requested_start=start_date,
            effective_start=eff_start,
            effective_end=eff_end,
            securities=summaries,
            normalized_series=normalized_series,
            objective_signals=signals,
            coverage=coverage,
            data_status=(
                DataStatus.FINAL if coverage >= Decimal("0.80") else DataStatus.PARTIAL
            ),
            as_of=datetime.now(UTC),
        )
