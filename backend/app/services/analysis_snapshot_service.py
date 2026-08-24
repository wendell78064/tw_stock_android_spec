from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.domain.analysis_snapshot import (
    ComparisonAnalysisSnapshot,
    ComparisonSecurityItem,
    CreditSnapshot,
    DataQualitySummary,
    DerivativesContextSnapshot,
    IndustryContextSnapshot,
    InstitutionalNetSnapshot,
    InstitutionalSnapshot,
    MarketContextSnapshot,
    PortfolioPositionSnapshot,
    PriceSnapshot,
    PromptSectionStatus,
    ReturnsSnapshot,
    SecurityAnalysisSnapshot,
    SecurityIdentitySnapshot,
    TechnicalSnapshotData,
)
from app.domain.market_spot import InstitutionType, MarketSpotRepository
from app.domain.pricing import CandleInterval, PriceBasis, PriceRepository, SecurityKey
from app.domain.security import MarketCode, SecurityRepository
from app.repositories.models import (
    IndustryModel,
    PortfolioModel,
    PortfolioTransactionModel,
    SecurityModel,
    TaxonomyStrengthSnapshotModel,
)
from app.services.candle_aggregation import CandleAggregationService
from app.services.market_spot import CreditTradingService, InstitutionalService
from app.services.portfolio import PortfolioAccountingService
from app.services.technical_indicators import TechnicalIndicatorService, TechnicalParameters


class AnalysisSnapshotService:
    def __init__(
        self,
        session: AsyncSession,
        security_repo: SecurityRepository,
        price_repo: PriceRepository,
        market_spot_repo: MarketSpotRepository,
    ):
        self.session = session
        self.security_repo = security_repo
        self.price_repo = price_repo
        self.market_spot_repo = market_spot_repo

    async def build_snapshot(
        self,
        code: str,
        market: MarketCode,
        user_id: UUID | None = None,
    ) -> SecurityAnalysisSnapshot:
        # 1. Resolve security
        securities = await self.security_repo.find_by_code(code, market)
        if not securities:
            raise AppError(
                "SECURITY_NOT_FOUND", "找不到指定股票", 404, {"code": code, "market": market.value}
            )
        sec = securities[0]

        # Fetch theme names from domain security
        theme_names = [t.name for t in sec.themes] if sec.themes else []

        sec_type_str = (
            sec.security_type.value
            if hasattr(sec.security_type, "value")
            else str(sec.security_type)
        )
        sec_identity = SecurityIdentitySnapshot(
            code=sec.code,
            name=sec.name,
            market=sec.market,
            security_type=sec_type_str,
            primary_industry=sec.primary_industry,
            themes=theme_names,
            listing_date=sec.listing_date,
        )

        now = datetime.now(UTC)
        key = SecurityKey(market, code)

        # 2. Price and Returns
        prices = await self.price_repo.list_prices(key, None, None)
        price_snap: PriceSnapshot | None = None
        returns_snap = ReturnsSnapshot(data_status=PromptSectionStatus.NO_DATA)

        as_of_time = now

        if prices:
            latest_price = prices[-1]
            as_of_time = latest_price.as_of
            price_snap = PriceSnapshot(
                trade_date=latest_price.trade_date,
                close=latest_price.close,
                open=latest_price.open,
                high=latest_price.high,
                low=latest_price.low,
                volume_shares=latest_price.volume_shares,
                turnover_amount=latest_price.turnover_amount,
                data_status=latest_price.data_status,
                as_of=latest_price.as_of,
            )

            # Calculate returns: 1D, 5D, 10D, 30D, 1Y
            valid_closes = [(p.trade_date, p.close) for p in prices if p.close is not None]
            if len(valid_closes) >= 1:
                cur_close = valid_closes[-1][1]

                def calc_ret(idx: int) -> Decimal | None:
                    if len(valid_closes) > idx and cur_close is not None:
                        past_close = valid_closes[-1 - idx][1]
                        if past_close and past_close > Decimal("0"):
                            return ((cur_close - past_close) / past_close) * Decimal("100")
                    return None

                returns_snap = ReturnsSnapshot(
                    return_1d=calc_ret(1),
                    return_5d=calc_ret(5),
                    return_10d=calc_ret(10),
                    return_30d=calc_ret(30),
                    return_1y=calc_ret(240),
                    data_status=PromptSectionStatus.COMPLETE,
                )

        # 3. Technicals
        tech_snap: TechnicalSnapshotData | None = None
        if prices:
            latest_trade_date = prices[-1].trade_date
            snapshots = await self.price_repo.list_technicals(
                key, PriceBasis.RAW, latest_trade_date, latest_trade_date
            )
            if snapshots:
                ts = snapshots[-1]
                v = ts.values
                tech_snap = TechnicalSnapshotData(
                    trade_date=latest_trade_date,
                    ma5=v.get("MA5"),
                    ma10=v.get("MA10"),
                    ma20=v.get("MA20"),
                    ma60=v.get("MA60"),
                    ma120=v.get("MA120"),
                    ma240=v.get("MA240"),
                    rsi=v.get("RSI14"),
                    macd=v.get("MACD"),
                    macd_signal=v.get("MACD_SIGNAL"),
                    macd_hist=v.get("MACD_HISTOGRAM"),
                    kd_k=v.get("KD_K"),
                    kd_d=v.get("KD_D"),
                    bollinger_upper=v.get("BBANDS_UPPER"),
                    bollinger_middle=v.get("BBANDS_MIDDLE"),
                    bollinger_lower=v.get("BBANDS_LOWER"),
                    atr=v.get("ATR14"),
                    williams_r=v.get("WILLIAMS_R"),
                    obv=v.get("OBV"),
                    data_status=PromptSectionStatus.COMPLETE,
                )
            else:
                candles = CandleAggregationService().aggregate(
                    prices, CandleInterval.DAY, PriceBasis.RAW
                )
                if candles:
                    series = TechnicalIndicatorService().calculate(
                        candles, TechnicalParameters()
                    )
                    if series.values:
                        v = series.values[-1]
                        tech_snap = TechnicalSnapshotData(
                            trade_date=latest_trade_date,
                            ma5=v.get("MA5"),
                            ma10=v.get("MA10"),
                            ma20=v.get("MA20"),
                            ma60=v.get("MA60"),
                            ma120=v.get("MA120"),
                            ma240=v.get("MA240"),
                            rsi=v.get("RSI14"),
                            macd=v.get("MACD"),
                            macd_signal=v.get("MACD_SIGNAL"),
                            macd_hist=v.get("MACD_HISTOGRAM"),
                            kd_k=v.get("KD_K"),
                            kd_d=v.get("KD_D"),
                            bollinger_upper=v.get("BBANDS_UPPER"),
                            bollinger_middle=v.get("BBANDS_MIDDLE"),
                            bollinger_lower=v.get("BBANDS_LOWER"),
                            atr=v.get("ATR14"),
                            williams_r=v.get("WILLIAMS_R"),
                            obv=v.get("OBV"),
                            data_status=PromptSectionStatus.COMPLETE,
                        )

        # 4. Institutional
        inst_snap: InstitutionalSnapshot | None = None
        try:
            inst_series = await InstitutionalService(self.market_spot_repo).series(
                market, key, 20
            )
            if inst_series:
                by_date: dict[date, dict[str, int]] = {}
                consecutive_foreign = 0
                consecutive_trust = 0
                dates_sorted = sorted(list({p.trade_date for p in inst_series}))

                for p in inst_series:
                    d = p.trade_date
                    if d not in by_date:
                        by_date[d] = {"foreign": 0, "trust": 0, "dealer": 0}
                    itype = p.institution_type
                    net_val = p.net or 0
                    if itype in (InstitutionType.FOREIGN, InstitutionType.FOREIGN_DEALER):
                        by_date[d]["foreign"] += net_val
                    elif itype == InstitutionType.INVESTMENT_TRUST:
                        by_date[d]["trust"] += net_val
                    elif itype == InstitutionType.DEALER:
                        by_date[d]["dealer"] += net_val

                if dates_sorted:
                    latest_d = dates_sorted[-1]
                    ld_data = by_date.get(latest_d, {"foreign": 0, "trust": 0, "dealer": 0})
                    tot_1d = ld_data["foreign"] + ld_data["trust"] + ld_data["dealer"]
                    latest_net = InstitutionalNetSnapshot(
                        foreign_net_shares=ld_data["foreign"],
                        trust_net_shares=ld_data["trust"],
                        dealer_net_shares=ld_data["dealer"],
                        total_net_shares=tot_1d,
                    )

                    d_5 = dates_sorted[-5:]
                    f_5 = sum(by_date[d]["foreign"] for d in d_5)
                    t_5 = sum(by_date[d]["trust"] for d in d_5)
                    dl_5 = sum(by_date[d]["dealer"] for d in d_5)
                    cum_5d = InstitutionalNetSnapshot(f_5, t_5, dl_5, f_5 + t_5 + dl_5)

                    d_10 = dates_sorted[-10:]
                    f_10 = sum(by_date[d]["foreign"] for d in d_10)
                    t_10 = sum(by_date[d]["trust"] for d in d_10)
                    dl_10 = sum(by_date[d]["dealer"] for d in d_10)
                    cum_10d = InstitutionalNetSnapshot(f_10, t_10, dl_10, f_10 + t_10 + dl_10)

                    for p in reversed(inst_series):
                        if (
                            p.institution_type == InstitutionType.FOREIGN
                            and consecutive_foreign == 0
                        ):
                            consecutive_foreign = p.consecutive_direction_days
                        if (
                            p.institution_type == InstitutionType.INVESTMENT_TRUST
                            and consecutive_trust == 0
                        ):
                            consecutive_trust = p.consecutive_direction_days

                    inst_snap = InstitutionalSnapshot(
                        trade_date=latest_d,
                        latest_day=latest_net,
                        cum_5d=cum_5d,
                        cum_10d=cum_10d,
                        consecutive_foreign_days=consecutive_foreign,
                        consecutive_trust_days=consecutive_trust,
                        data_status=PromptSectionStatus.COMPLETE,
                    )
        except Exception:
            pass

        # 5. Credit
        credit_snap: CreditSnapshot | None = None
        try:
            credit_series = await CreditTradingService(self.market_spot_repo).series(
                market, key, 20
            )
            if credit_series:
                margins = credit_series.margins
                lending = credit_series.lending
                m_last = margins[-1] if margins else None
                l_last = lending[-1] if lending else None
                latest_d = (
                    m_last.trade_date if m_last else (l_last.trade_date if l_last else None)
                )

                st = (
                    PromptSectionStatus.COMPLETE
                    if (m_last or l_last)
                    else PromptSectionStatus.NO_DATA
                )
                credit_snap = CreditSnapshot(
                    trade_date=latest_d,
                    margin_balance=m_last.margin_balance if m_last else None,
                    margin_change=m_last.margin_balance_change if m_last else None,
                    short_balance=m_last.short_balance if m_last else None,
                    short_change=m_last.short_balance_change if m_last else None,
                    short_margin_ratio=m_last.short_margin_ratio if m_last else None,
                    lending_balance=l_last.lending_balance if l_last else None,
                    lending_change=l_last.lending_balance_change if l_last else None,
                    data_status=st,
                )
        except Exception:
            pass

        # 6. Industry Context
        industry_snap: IndustryContextSnapshot | None = None
        if sec.primary_industry:
            try:
                stmt = (
                    select(TaxonomyStrengthSnapshotModel)
                    .join(
                        IndustryModel,
                        TaxonomyStrengthSnapshotModel.taxonomy_id == IndustryModel.id,
                    )
                    .where(IndustryModel.name == sec.primary_industry)
                    .order_by(TaxonomyStrengthSnapshotModel.trade_date.desc())
                    .limit(1)
                )
                res = (await self.session.execute(stmt)).scalar_one_or_none()
                if res:
                    rep_stmt = (
                        select(SecurityModel.name, SecurityModel.code)
                        .join(IndustryModel, SecurityModel.industry_id == IndustryModel.id)
                        .where(
                            IndustryModel.name == sec.primary_industry,
                            SecurityModel.is_active.is_(True),
                        )
                        .limit(5)
                    )
                    reps = [
                        f"{r[0]}({r[1]})" for r in (await self.session.execute(rep_stmt)).all()
                    ]

                    industry_snap = IndustryContextSnapshot(
                        industry_name=sec.primary_industry,
                        rank=res.rank,
                        total_industries=33,
                        strength_score=res.strength_score,
                        representative_stocks=reps,
                        data_status=PromptSectionStatus.COMPLETE,
                    )
            except Exception:
                pass
        if not industry_snap and sec.primary_industry:
            industry_snap = IndustryContextSnapshot(
                industry_name=sec.primary_industry,
                data_status=PromptSectionStatus.NO_DATA,
            )

        # 7. Market Context & Derivatives
        market_snap: MarketContextSnapshot | None = None
        deriv_snap: DerivativesContextSnapshot | None = None
        try:
            breadth_rows = await self.market_spot_repo.breadth("TWSE", None, None, 1)
            inst_spot_rows = await self.market_spot_repo.institutional(MarketCode.TWSE, 1)
            idx_rows = await self.market_spot_repo.indexes("TAIEX", None, None, 1)

            b_last = breadth_rows[-1] if breadth_rows else None
            i_last = idx_rows[-1] if idx_rows else None
            tot_inst_spot = (
                sum((item.net for item in inst_spot_rows), Decimal("0"))
                if inst_spot_rows
                else None
            )

            latest_mkt_d = (
                b_last.trade_date if b_last else (i_last.trade_date if i_last else None)
            )
            st_mkt = (
                PromptSectionStatus.COMPLETE
                if (b_last or i_last)
                else PromptSectionStatus.NO_DATA
            )
            market_snap = MarketContextSnapshot(
                trade_date=latest_mkt_d,
                taiex_close=i_last.close if i_last else None,
                taiex_change_pct=i_last.change_pct if i_last else None,
                advances_count=b_last.advances if b_last else None,
                declines_count=b_last.declines if b_last else None,
                unchanged_count=b_last.unchanged if b_last else None,
                institutional_spot_net=tot_inst_spot,
                data_status=st_mkt,
            )
        except Exception:
            pass

        # 8. Portfolio Position
        pos_snap: PortfolioPositionSnapshot | None = None
        if user_id:
            try:
                pos_stmt = select(PortfolioModel).where(PortfolioModel.user_id == user_id)
                portfolios = list((await self.session.execute(pos_stmt)).scalars().all())
                total_shares = 0
                weighted_cost_sum = Decimal("0")

                for pf in portfolios:
                    tx_stmt = select(PortfolioTransactionModel).where(
                        PortfolioTransactionModel.portfolio_id == pf.id
                    )
                    tx_models = list((await self.session.execute(tx_stmt)).scalars().all())
                    if tx_models:
                        service = PortfolioAccountingService(
                            transactions=[tx.to_domain() for tx in tx_models]
                        )
                        pos = service.positions.get(key)
                        if pos and pos.quantity > 0:
                            total_shares += pos.quantity
                            weighted_cost_sum += pos.average_cost * Decimal(pos.quantity)

                if total_shares > 0:
                    avg_cost = weighted_cost_sum / Decimal(total_shares)
                    cur_price = (
                        price_snap.close if (price_snap and price_snap.close) else avg_cost
                    )
                    cur_val = cur_price * Decimal(total_shares)
                    cost_val = avg_cost * Decimal(total_shares)
                    unrealized = cur_val - cost_val
                    unrealized_pct = (
                        (unrealized / cost_val) * Decimal("100")
                        if cost_val > Decimal("0")
                        else Decimal("0")
                    )

                    pos_snap = PortfolioPositionSnapshot(
                        shares=total_shares,
                        moving_average_cost=avg_cost,
                        latest_market_value=cur_val,
                        unrealized_pnl=unrealized,
                        unrealized_pnl_pct=unrealized_pct,
                        as_of=as_of_time,
                    )
            except Exception:
                pass

        # 9. Data Quality Summary
        notes: list[str] = []
        comp_count = 0
        total_sections = 7

        if price_snap and price_snap.close is not None:
            comp_count += 1
        else:
            notes.append("缺少最新收盤價格")

        if returns_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1
        else:
            notes.append("歷史區間報酬不完整")

        if tech_snap and tech_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1
        else:
            notes.append("技術指標快照未完全計算")

        if inst_snap and inst_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1
        else:
            notes.append("三大法人籌碼資料未提供")

        if credit_snap and credit_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1
        else:
            notes.append("信用交易或借券資料未提供")

        if market_snap and market_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1

        if industry_snap and industry_snap.data_status == PromptSectionStatus.COMPLETE:
            comp_count += 1

        comp_pct = (Decimal(comp_count) / Decimal(total_sections)) * Decimal("100")
        if comp_count >= 5:
            overall_dq = PromptSectionStatus.COMPLETE
        elif comp_count >= 2:
            overall_dq = PromptSectionStatus.PARTIAL
        else:
            overall_dq = PromptSectionStatus.UNAVAILABLE

        dq_summary = DataQualitySummary(
            overall_status=overall_dq,
            completeness_pct=round(comp_pct, 1),
            freshness_notes=notes,
        )

        return SecurityAnalysisSnapshot(
            as_of=as_of_time,
            generated_at=now,
            market=market,
            security=sec_identity,
            price=price_snap,
            returns=returns_snap,
            technicals=tech_snap,
            institutional=inst_snap,
            credit=credit_snap,
            industry=industry_snap,
            market_context=market_snap,
            derivatives_context=deriv_snap,
            portfolio_position=pos_snap,
            data_quality=dq_summary,
        )

    async def build_comparison_snapshot(
        self, items: list[ComparisonSecurityItem], user_id: UUID | None = None
    ) -> ComparisonAnalysisSnapshot:
        if len(items) < 2:
            raise ValueError("Comparison requires at least 2 securities")
        if len(items) > 5:
            raise ValueError("Comparison allows at most 5 securities")

        snapshots: list[SecurityAnalysisSnapshot] = []
        for item in items:
            snap = await self.build_snapshot(item.code, item.market, user_id=user_id)
            snapshots.append(snap)

        now = datetime.now(UTC)
        unified_mkt = snapshots[0].market_context if snapshots else None
        unified_deriv = snapshots[0].derivatives_context if snapshots else None

        return ComparisonAnalysisSnapshot(
            generated_at=now,
            snapshots=snapshots,
            unified_market_context=unified_mkt,
            unified_derivatives_context=unified_deriv,
        )
