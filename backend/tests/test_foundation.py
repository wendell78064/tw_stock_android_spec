from datetime import date
from decimal import Decimal

import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.weekend_calendar import WeekendOnlyCalendar
from app.domain.market_data import DataStatus


@pytest.mark.asyncio
async def test_fake_provider_discloses_missing_data_without_fabricating_price() -> None:
    snapshot = await FakeMarketDataProvider().get_snapshot("TEST")
    assert snapshot.price is None
    assert snapshot.data_status is DataStatus.UNAVAILABLE
    assert snapshot.missing_reason
    assert not isinstance(snapshot.price, float)


def test_decimal_financial_type() -> None:
    value = Decimal("470.10") + Decimal("0.20")
    assert value == Decimal("470.30")


def test_calendar_abstraction_skips_weekend() -> None:
    calendar = WeekendOnlyCalendar()
    assert calendar.previous_trading_day(date(2026, 8, 10)) == date(2026, 8, 7)

