from datetime import date
from decimal import Decimal

import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.domain.pricing import CandleInterval, PriceBasis, SecurityKey
from app.domain.security import MarketCode
from app.services.candle_aggregation import CandleAggregationService


@pytest.mark.asyncio
async def test_week_and_month_ohlcv_cross_month_without_holiday_fill() -> None:
    records = await FakeMarketDataProvider().get_daily_prices(
        security=SecurityKey(MarketCode.TWSE, "1234"),
        start_date=date(2026, 7, 27),
        end_date=date(2026, 8, 7),
    )
    service = CandleAggregationService()
    weeks = service.aggregate(records, CandleInterval.WEEK, PriceBasis.RAW)
    months = service.aggregate(records, CandleInterval.MONTH, PriceBasis.RAW)
    assert len(weeks) == 2 and len(months) == 2
    assert weeks[0].open == records[0].open and weeks[0].close == records[4].close
    assert weeks[0].high == max(item.high for item in records[:5])
    assert weeks[0].volume_shares == sum(item.volume_shares for item in records[:5])
    assert all(item.trade_date.weekday() < 5 for item in weeks)
    assert isinstance(months[0].turnover_amount, Decimal)
