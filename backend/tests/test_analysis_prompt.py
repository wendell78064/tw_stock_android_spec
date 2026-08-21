from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.analysis_snapshot import (
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
from app.domain.market_data import DataStatus
from app.domain.market_spot import MarketSpotRepository
from app.domain.pricing import DailyPriceRecord, PriceRepository, SecurityKey
from app.domain.security import (
    MarketCode,
    Security,
    SecurityRepository,
    SecurityStatus,
    SecurityType,
)
from app.services.analysis_snapshot_service import AnalysisSnapshotService
from app.services.individual_prompt_builder import IndividualAnalysisPromptBuilder


def _build_dummy_security(
    code: str = "2330", market: MarketCode = MarketCode.TWSE
) -> Security:
    now = datetime.now(UTC)
    return Security(
        id=uuid4(),
        market=market,
        code=code,
        name="台積電",
        security_type=SecurityType.COMMON_STOCK,
        status=SecurityStatus.ACTIVE,
        is_active=True,
        listing_date=date(1994, 9, 5),
        primary_industry="半導體業",
        source_code="TWSE_SECURITY_MASTER",
        as_of=now,
        received_at=now,
        data_status=DataStatus.FINAL,
        themes=[],
    )


@pytest.fixture
def dummy_snapshot() -> SecurityAnalysisSnapshot:
    now = datetime(2026, 8, 20, 15, 30, 0, tzinfo=UTC)
    sec = SecurityIdentitySnapshot(
        code="2330",
        name="台積電",
        market=MarketCode.TWSE,
        security_type="COMMON_STOCK",
        primary_industry="半導體業",
        themes=["AI伺服器", "先進製程"],
        listing_date=date(1994, 9, 5),
    )
    price = PriceSnapshot(
        trade_date=date(2026, 8, 20),
        close=Decimal("980.0"),
        open=Decimal("975.0"),
        high=Decimal("985.0"),
        low=Decimal("970.0"),
        volume_shares=16967737,
        turnover_amount=Decimal("40117420293"),
        data_status=DataStatus.FINAL,
        as_of=now,
    )
    returns = ReturnsSnapshot(
        return_1d=Decimal("1.55"),
        return_5d=Decimal("3.20"),
        return_10d=Decimal("5.10"),
        return_30d=Decimal("8.40"),
        return_1y=Decimal("42.50"),
        data_status=PromptSectionStatus.COMPLETE,
    )
    tech = TechnicalSnapshotData(
        trade_date=date(2026, 8, 20),
        ma5=Decimal("970.0"),
        ma10=Decimal("965.0"),
        ma20=Decimal("955.0"),
        ma60=Decimal("940.0"),
        ma120=Decimal("900.0"),
        ma240=Decimal("820.0"),
        rsi=Decimal("68.5"),
        macd=Decimal("12.4"),
        macd_signal=Decimal("10.2"),
        macd_hist=Decimal("2.2"),
        kd_k=Decimal("78.0"),
        kd_d=Decimal("72.0"),
        bollinger_upper=Decimal("995.0"),
        bollinger_middle=Decimal("955.0"),
        bollinger_lower=Decimal("915.0"),
        atr=Decimal("18.5"),
        williams_r=Decimal("-15.0"),
        obv=Decimal("12500000"),
        data_status=PromptSectionStatus.COMPLETE,
    )
    inst = InstitutionalSnapshot(
        trade_date=date(2026, 8, 20),
        latest_day=InstitutionalNetSnapshot(5000000, 1200000, -300000, 5900000),
        cum_5d=InstitutionalNetSnapshot(15000000, 3500000, -500000, 18000000),
        cum_10d=InstitutionalNetSnapshot(28000000, 6000000, -800000, 33200000),
        consecutive_foreign_days=3,
        consecutive_trust_days=5,
        data_status=PromptSectionStatus.COMPLETE,
    )
    credit = CreditSnapshot(
        trade_date=date(2026, 8, 20),
        margin_balance=25000,
        margin_change=-450,
        short_balance=1200,
        short_change=50,
        short_margin_ratio=Decimal("4.80"),
        lending_balance=1500000,
        lending_change=-20000,
        data_status=PromptSectionStatus.COMPLETE,
    )
    industry = IndustryContextSnapshot(
        industry_name="半導體業",
        rank=2,
        total_industries=33,
        strength_score=Decimal("78.5"),
        representative_stocks=["聯發科(2454)", "聯電(2303)"],
        data_status=PromptSectionStatus.COMPLETE,
    )
    market_ctx = MarketContextSnapshot(
        trade_date=date(2026, 8, 20),
        taiex_close=Decimal("22450.0"),
        taiex_change_pct=Decimal("0.85"),
        advances_count=580,
        declines_count=320,
        unchanged_count=95,
        institutional_spot_net=Decimal("15200000000"),
        data_status=PromptSectionStatus.COMPLETE,
    )
    deriv_ctx = DerivativesContextSnapshot(
        trade_date=date(2026, 8, 20),
        tx_close=Decimal("22480.0"),
        foreign_futures_net_oi=-28500,
        option_put_call_ratio=Decimal("112.5"),
        top10_trader_concentration_pct=Decimal("54.2"),
        vix_status="UNAVAILABLE",
        data_status=PromptSectionStatus.COMPLETE,
    )
    pos = PortfolioPositionSnapshot(
        shares=2000,
        moving_average_cost=Decimal("850.0"),
        latest_market_value=Decimal("1960000.0"),
        unrealized_pnl=Decimal("260000.0"),
        unrealized_pnl_pct=Decimal("15.29"),
        as_of=now,
    )
    dq = DataQualitySummary(
        overall_status=PromptSectionStatus.COMPLETE,
        completeness_pct=Decimal("100.0"),
        freshness_notes=[],
    )
    return SecurityAnalysisSnapshot(
        as_of=now,
        generated_at=now,
        market=MarketCode.TWSE,
        security=sec,
        price=price,
        returns=returns,
        technicals=tech,
        institutional=inst,
        credit=credit,
        industry=industry,
        market_context=market_ctx,
        derivatives_context=deriv_ctx,
        portfolio_position=pos,
        data_quality=dq,
    )


def test_individual_prompt_builder_structure_and_bounded_size(
    dummy_snapshot: SecurityAnalysisSnapshot,
) -> None:
    builder = IndividualAnalysisPromptBuilder()
    prompt = builder.build_prompt(dummy_snapshot)

    assert "【TW Market Ledger 智慧台股量化分析 Prompt】" in prompt
    assert "台積電 (2330)" in prompt
    assert "半導體業" in prompt
    assert "980.00 元" in prompt
    assert "MA240 (年線): 820.00" in prompt
    assert "外資 5,000.00" in prompt
    assert "加權指數 (TAIEX)：22,450.00 點" in prompt
    assert "持股狀態：【已持有】" in prompt
    assert "移動平均成本：850.00 元" in prompt
    assert "12. 【具體操作策略與風控指引】" in prompt

    # Verify size is bounded (between 1,000 and 4,500 characters)
    char_len = len(prompt)
    assert 1000 < char_len < 4500, f"Prompt character count {char_len} out of expected bounds"


def test_individual_prompt_builder_handles_null_portfolio_and_unavailable_sections(
    dummy_snapshot: SecurityAnalysisSnapshot,
) -> None:
    # Modify snapshot to simulate missing portfolio, null MA240, and unavailable credit
    snapshot_without_pos = SecurityAnalysisSnapshot(
        as_of=dummy_snapshot.as_of,
        generated_at=dummy_snapshot.generated_at,
        market=dummy_snapshot.market,
        security=dummy_snapshot.security,
        price=dummy_snapshot.price,
        returns=dummy_snapshot.returns,
        technicals=TechnicalSnapshotData(
            trade_date=date(2026, 8, 20),
            ma5=Decimal("970.0"),
            ma10=Decimal("965.0"),
            ma20=Decimal("955.0"),
            ma60=Decimal("940.0"),
            ma120=Decimal("900.0"),
            ma240=None,  # Null MA240 due to insufficient history
            rsi=Decimal("68.5"),
            data_status=PromptSectionStatus.COMPLETE,
        ),
        institutional=None,
        credit=None,
        industry=dummy_snapshot.industry,
        market_context=dummy_snapshot.market_context,
        derivatives_context=dummy_snapshot.derivatives_context,
        portfolio_position=None,  # Not held
        data_quality=DataQualitySummary(
            overall_status=PromptSectionStatus.PARTIAL,
            completeness_pct=Decimal("70.0"),
            freshness_notes=["三大法人籌碼資料未提供", "信用交易或借券資料未提供"],
        ),
    )

    builder = IndividualAnalysisPromptBuilder()
    prompt = builder.build_prompt(snapshot_without_pos)

    assert "持股狀態：【未持有 / 觀察名單標的】" in prompt
    assert "MA240 (年線): NULL" in prompt
    assert "三大法人數據：UNAVAILABLE / 暫無資料" in prompt
    assert "信用交易與借券數據：UNAVAILABLE / 暫無資料" in prompt
    assert "嚴禁自行將其視為 0 進行計算或推論。" in prompt


@pytest.mark.asyncio
async def test_analysis_snapshot_service_builds_snapshot() -> None:
    session = AsyncMock()
    sec_repo = AsyncMock(spec=SecurityRepository)
    price_repo = AsyncMock(spec=PriceRepository)
    market_spot_repo = AsyncMock(spec=MarketSpotRepository)

    sec = _build_dummy_security("2330", MarketCode.TWSE)
    sec_repo.find_by_code.return_value = [sec]

    # Mock prices
    p1 = DailyPriceRecord(
        security=SecurityKey(MarketCode.TWSE, "2330"),
        trade_date=date(2026, 8, 19),
        open=Decimal("960.0"),
        high=Decimal("970.0"),
        low=Decimal("955.0"),
        close=Decimal("965.0"),
        adjusted_open=Decimal("960.0"),
        adjusted_high=Decimal("970.0"),
        adjusted_low=Decimal("955.0"),
        adjusted_close=Decimal("965.0"),
        volume_shares=15000000,
        turnover_amount=Decimal("35000000000"),
        source_code="TWSE_DAILY",
        as_of=datetime.now(UTC),
        received_at=datetime.now(UTC),
        data_status=DataStatus.FINAL,
    )
    p2 = DailyPriceRecord(
        security=SecurityKey(MarketCode.TWSE, "2330"),
        trade_date=date(2026, 8, 20),
        open=Decimal("970.0"),
        high=Decimal("985.0"),
        low=Decimal("968.0"),
        close=Decimal("980.0"),
        adjusted_open=Decimal("970.0"),
        adjusted_high=Decimal("985.0"),
        adjusted_low=Decimal("968.0"),
        adjusted_close=Decimal("980.0"),
        volume_shares=16967737,
        turnover_amount=Decimal("40117420293"),
        source_code="TWSE_DAILY",
        as_of=datetime.now(UTC),
        received_at=datetime.now(UTC),
        data_status=DataStatus.FINAL,
    )
    price_repo.list_prices.return_value = [p1, p2]
    price_repo.list_technicals.return_value = []

    # Mock DB query executions
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_res.all.return_value = []
    session.execute.return_value = mock_res

    # Mock spot queries
    market_spot_repo.institutional.return_value = []
    market_spot_repo.breadth.return_value = []
    market_spot_repo.indexes.return_value = []

    service = AnalysisSnapshotService(session, sec_repo, price_repo, market_spot_repo)
    snapshot = await service.build_snapshot("2330", MarketCode.TWSE)

    assert snapshot.security.code == "2330"
    assert snapshot.security.name == "台積電"
    assert snapshot.price is not None
    assert snapshot.price.close == Decimal("980.0")
    assert snapshot.returns.return_1d is not None
    assert snapshot.data_quality.overall_status in (
        PromptSectionStatus.COMPLETE,
        PromptSectionStatus.PARTIAL,
    )


@pytest.mark.asyncio
async def test_analysis_snapshot_service_tpex_security() -> None:
    session = AsyncMock()
    sec_repo = AsyncMock(spec=SecurityRepository)
    price_repo = AsyncMock(spec=PriceRepository)
    market_spot_repo = AsyncMock(spec=MarketSpotRepository)

    sec = _build_dummy_security("6488", MarketCode.TPEX)
    sec_repo.find_by_code.return_value = [sec]
    price_repo.list_prices.return_value = []
    price_repo.list_technicals.return_value = []

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.scalar_one_or_none.return_value = None
    mock_res.all.return_value = []
    session.execute.return_value = mock_res

    market_spot_repo.institutional.return_value = []
    market_spot_repo.breadth.return_value = []
    market_spot_repo.indexes.return_value = []

    service = AnalysisSnapshotService(session, sec_repo, price_repo, market_spot_repo)
    snapshot = await service.build_snapshot("6488", MarketCode.TPEX)

    assert snapshot.security.code == "6488"
    assert snapshot.security.market == MarketCode.TPEX
    builder = IndividualAnalysisPromptBuilder()
    prompt = builder.build_prompt(snapshot)
    assert "證券櫃檯買賣中心 (上櫃 TPEX)" in prompt

