from datetime import UTC, date, datetime

import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.domain.market_data import DataStatus
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode

DAY = date(2026, 8, 7)
NOW = datetime(2026, 8, 7, 10, tzinfo=UTC)


def test_twse_daily_mapping_decimal_and_no_trade() -> None:
    provider = TwseSecurityProvider()
    item = provider.map_daily_row(
        {
            "證券代號": "1234",
            "開盤價": "40.10",
            "最高價": "42.00",
            "最低價": "39.50",
            "收盤價": "41.20",
            "成交股數": "100,000",
            "成交金額": "4,120,000",
        },
        trade_date=DAY,
        received_at=NOW,
    )
    assert item is not None and str(item.close) == "41.20" and item.volume_shares == 100000
    halted = provider.map_daily_row(
        {
            "證券代號": "1234",
            "開盤價": "--",
            "最高價": "--",
            "最低價": "--",
            "收盤價": "--",
            "成交股數": "0",
            "成交金額": "0",
        },
        trade_date=DAY,
        received_at=NOW,
    )
    assert (
        halted is not None and halted.close is None and halted.data_status is DataStatus.UNAVAILABLE
    )


def test_tpex_daily_mapping_and_missing_code() -> None:
    provider = TpexSecurityProvider()
    item = provider.map_daily_row(
        {
            "SecuritiesCompanyCode": "5678",
            "Open": "50",
            "High": "52",
            "Low": "49",
            "Close": "51",
            "TradingShares": "200000",
            "TransactionAmount": "10200000",
        },
        trade_date=DAY,
        received_at=NOW,
    )
    assert item is not None and item.security.market is MarketCode.TPEX
    assert provider.map_daily_row({}, trade_date=DAY, received_at=NOW) is None


@pytest.mark.asyncio
async def test_fake_daily_provider_is_deterministic_adjusted_and_skips_weekends() -> None:
    key = SecurityKey(MarketCode.TWSE, "1234")
    first = await FakeMarketDataProvider().get_daily_prices(
        security=key, start_date=date(2026, 8, 1), end_date=DAY
    )
    second = await FakeMarketDataProvider().get_daily_prices(
        security=key, start_date=date(2026, 8, 1), end_date=DAY
    )
    assert first == second and len(first) == 5
    assert all(item.trade_date.weekday() < 5 and item.adjusted_close is not None for item in first)
