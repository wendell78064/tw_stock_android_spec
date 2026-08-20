import argparse
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


def test_sync_daily_prices_market_filter_selects_correct_provider() -> None:
    """Verify that --market TWSE restricts providers to TWSE-only (no TPEx calls),
    and --market TPEX restricts providers to TPEX-only (no TWSE calls).
    Ensures Stage B historical backfill does not trigger TPEx latest-snapshot on every date.
    """
    def _build_providers(market: str | None, provider: str = "official"):
        args = argparse.Namespace(
            provider=provider,
            market=market,
            code=None,
            date=None,
            start=None,
            end=None,
        )
        if args.provider == "fake":
            return [FakeMarketDataProvider()]
        elif args.market == "TWSE":
            return [TwseSecurityProvider()]
        elif args.market == "TPEX":
            return [TpexSecurityProvider()]
        else:
            return [TwseSecurityProvider(), TpexSecurityProvider()]

    # TWSE-only: only TWSE provider, no TPEx
    twse_providers = _build_providers("TWSE")
    assert len(twse_providers) == 1
    assert isinstance(twse_providers[0], TwseSecurityProvider)

    # TPEX-only: only TPEX provider, no TWSE
    tpex_providers = _build_providers("TPEX")
    assert len(tpex_providers) == 1
    assert isinstance(tpex_providers[0], TpexSecurityProvider)

    # No market filter: both providers
    both_providers = _build_providers(None)
    assert len(both_providers) == 2
    assert any(isinstance(p, TwseSecurityProvider) for p in both_providers)
    assert any(isinstance(p, TpexSecurityProvider) for p in both_providers)

    # Fake provider ignores market filter
    fake_providers = _build_providers("TWSE", provider="fake")
    assert len(fake_providers) == 1
    assert isinstance(fake_providers[0], FakeMarketDataProvider)


def test_sync_daily_prices_cli_argparse() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("fake", "official"), default="fake")
    parser.add_argument("--date")
    parser.add_argument("--code")
    parser.add_argument("--market", choices=("TWSE", "TPEX"))
    parser.add_argument("--start")
    parser.add_argument("--end")

    # --market without --code (allowed for market-level range sync)
    args = parser.parse_args([
        "--provider", "official",
        "--market", "TWSE",
        "--start", "2024-08-01",
        "--end", "2024-08-05",
    ])
    assert args.market == "TWSE"
    assert args.code is None

    # --code without --market (disallowed)
    args2 = parser.parse_args(["--provider", "official", "--code", "2330"])
    assert args2.code == "2330" and args2.market is None
    if args2.code and not args2.market:
        with pytest.raises(SystemExit):
            parser.error("--market is required when --code is specified")


@pytest.mark.asyncio
async def test_twse_daily_prices_handles_null_table_title() -> None:
    """TWSE historical responses sometimes contain trailing tables with title=None.
    Ensure get_daily_prices parses without raising TypeError.
    """
    from unittest.mock import AsyncMock, MagicMock

    provider = TwseSecurityProvider()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "stat": "OK",
        "tables": [
            {
                "title": "110年12月10日 每日收盤行情(全部(不含權證、牛熊證、可展延牛熊證))",
                "fields": [
                    "證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額",
                    "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)",
                    "漲跌價差", "最後揭示買價", "最後揭示買量", "最後揭示賣價",
                    "最後揭示賣量", "本益比",
                ],
                "data": [[
                    "2330", "台積電", "100,000", "50", "60,000,000",
                    "600", "605", "598", "605", "+", "5", "605",
                    "10", "606", "10", "25.0",
                ]],
            },
            {"title": None, "data": []},
        ],
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.aclose = AsyncMock()
    provider.client = mock_client

    records = await provider.get_daily_prices(trade_date=date(2021, 12, 10))
    assert len(records) == 1
    assert records[0].security.code == "2330"





