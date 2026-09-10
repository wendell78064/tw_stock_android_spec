from datetime import UTC, datetime

import httpx
import pytest

from app.adapters.fake_market_data import FakeMarketDataProvider
from app.adapters.tpex.security_provider import TpexSecurityProvider
from app.adapters.twse.security_provider import TwseSecurityProvider
from app.domain.security import MarketCode, SecurityType

NOW = datetime(2026, 8, 6, tzinfo=UTC)


def test_twse_provider_maps_official_fields_and_filters_non_common_stock() -> None:
    provider = TwseSecurityProvider()
    record = provider.map_row(
        {
            "公司代號": "1234",
            "公司簡稱": "測試科技",
            "產業別": "24",
            "產業別名稱": "測試科技業",
            "上市日期": "1120102",
        },
        as_of=NOW,
        received_at=NOW,
    )
    assert record is not None
    assert record.market is MarketCode.TWSE
    assert record.security_type is SecurityType.COMMON_STOCK
    assert record.listing_date.isoformat() == "2023-01-02"
    assert (
        provider.map_row({"公司代號": "0050", "公司簡稱": "排除ETF"}, as_of=NOW, received_at=NOW)
        is None
    )
    assert (
        provider.map_row({"公司代號": "9103", "公司簡稱": "排除TDR"}, as_of=NOW, received_at=NOW)
        is None
    )
    # Legitimate 9-series common stocks
    rec_9904 = provider.map_row(
        {"公司代號": "9904", "公司簡稱": "寶成"}, as_of=NOW, received_at=NOW
    )
    assert rec_9904 is not None and rec_9904.code == "9904"
    rec_9802 = provider.map_row(
        {"公司代號": "9802", "公司簡稱": "鈺齊-KY"}, as_of=NOW, received_at=NOW
    )
    assert rec_9802 is not None and rec_9802.code == "9802"
    rec_9958 = provider.map_row(
        {"公司代號": "9958", "公司簡稱": "世紀鋼"}, as_of=NOW, received_at=NOW
    )
    assert rec_9958 is not None and rec_9958.code == "9958"


def test_tpex_provider_maps_official_fields() -> None:
    record = TpexSecurityProvider().map_row(
        {
            "SecuritiesCompanyCode": "5678",
            "CompanyAbbreviation": "範例電子",
            "SecuritiesIndustryCode": "28",
            "SecuritiesIndustryName": "測試電子業",
            "DateOfListing": "1111220",
        },
        as_of=NOW,
        received_at=NOW,
    )
    assert record is not None
    assert record.market is MarketCode.TPEX
    assert record.industry.name == "測試電子業"


@pytest.mark.asyncio
async def test_fake_provider_is_fixed_and_has_quality_metadata() -> None:
    records = await FakeMarketDataProvider().list_securities()
    assert {(item.market, item.code) for item in records} == {
        (MarketCode.TWSE, "1234"),
        (MarketCode.TPEX, "5678"),
    }
    assert all(
        item.as_of.tzinfo is not None and item.source_code.startswith("FAKE_") for item in records
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "master_path", "industry_path", "master_row"),
    [
        (
            TwseSecurityProvider,
            "/v1/opendata/t187ap03_L",
            "/v1/opendata/t187ap05_L",
            {"公司代號": "1234", "公司簡稱": "測試", "產業別": "24"},
        ),
        (
            TpexSecurityProvider,
            "/openapi/v1/mopsfin_t187ap03_O",
            "/openapi/v1/mopsfin_t187ap05_O",
            {
                "SecuritiesCompanyCode": "1234",
                "CompanyAbbreviation": "測試",
                "SecuritiesIndustryCode": "24",
            },
        ),
    ],
)
async def test_official_provider_joins_industry_name_by_company_code(
    provider_type, master_path, industry_path, master_row
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == master_path:
            return httpx.Response(200, json=[master_row])
        assert request.url.path == industry_path
        return httpx.Response(
            200,
            json=[{"公司代號": "1234", "產業別": "半導體業"}],
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        records = await provider_type(client).list_securities()

    assert len(records) == 1
    assert records[0].industry is not None
    assert records[0].industry.code == "24"
    assert records[0].industry.name == "半導體業"
