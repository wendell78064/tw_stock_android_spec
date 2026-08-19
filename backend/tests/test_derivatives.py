from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from app.adapters.fake_derivatives import FakeDerivativesDataProvider
from app.adapters.official_http import OfficialJsonClient, UpstreamSchemaError
from app.adapters.taifex.provider import OfficialTaifexProvider
from app.domain.derivatives import (
    TAIWAN_VIX_POLICY,
    OptionStrikeOpenInterest,
    OptionType,
    RollMethod,
    VixSourceCapability,
)
from app.services.derivatives import ContinuousFuturesService, FuturesService, OptionMaxPainService
from app.services.derivatives_ingestion import (
    DERIVATIVE_DATASETS,
    DerivativesIngestionService,
    derivative_error,
)
from tests.fakes import FakeSession


class MemoryDerivativesRepository:
    def __init__(self):
        self.data = {name: [] for name in DERIVATIVE_DATASETS}

    @staticmethod
    def identity(row):
        return tuple(
            getattr(row, name, None)
            for name in (
                "code",
                "product_code",
                "contract_code",
                "trade_date",
                "institution_type",
                "contract_scope",
                "side",
                "top_n",
                "expiry",
                "option_type",
                "strike",
            )
        )

    async def synchronize(self, dataset, records, run_id: UUID):
        inserted = updated = 0
        for row in records:
            old = next(
                (x for x in self.data[dataset] if self.identity(x) == self.identity(row)), None
            )
            if old is None:
                self.data[dataset].append(row)
                inserted += 1
            elif old != row:
                self.data[dataset].remove(old)
                self.data[dataset].append(row)
                updated += 1
        return inserted, updated

    async def products(self, product_code=None):
        return [
            x for x in self.data["FUTURES_PRODUCTS"] if not product_code or x.code == product_code
        ]

    async def contracts(self, product_code):
        return [x for x in self.data["FUTURES_CONTRACTS"] if x.product_code == product_code]

    async def daily(self, product_code, contract_code, limit):
        rows = [
            x
            for x in self.data["FUTURES_DAILY"]
            if x.product_code == product_code
            and (not contract_code or x.contract_code == contract_code)
        ]
        return sorted(rows, key=lambda x: x.trade_date)[-limit:]

    async def positions(self, product_code, limit):
        rows = [x for x in self.data["FUTURES_INSTITUTIONAL"] if x.product_code == product_code]
        dates = sorted({x.trade_date for x in rows})[-limit:]
        return [x for x in rows if x.trade_date in dates]

    async def concentrations(self, product_code, limit):
        return [x for x in self.data["TRADER_CONCENTRATION"] if x.product_code == product_code][
            -limit * 4 :
        ]

    async def put_call(self, product_code, limit):
        return [x for x in self.data["OPTION_PUT_CALL"] if x.product_code == product_code][-limit:]

    async def strike_oi(self, product_code, expiry, trade_date):
        return [
            x
            for x in self.data["OPTION_STRIKE_OI"]
            if x.product_code == product_code
            and (not expiry or x.expiry == expiry)
            and (not trade_date or x.trade_date == trade_date)
        ]

    async def volatility(self, code, limit):
        return [x for x in self.data["VOLATILITY_INDEX"] if x.code == code][-limit:]


@pytest.mark.asyncio
async def test_official_vix_capability_requires_verified_reuse_rights() -> None:
    provider = OfficialTaifexProvider()
    assert await provider.get_volatility_index(date(2026, 8, 7)) == []
    assert provider.vix_source_capability is VixSourceCapability.OFFICIAL_DOWNLOAD
    assert TAIWAN_VIX_POLICY.source_capability.value == "LICENSE_REQUIRED"
    assert TAIWAN_VIX_POLICY.license_status.value == "PUBLIC_DOWNLOAD_UNVERIFIED_REUSE"
    assert TAIWAN_VIX_POLICY.automation_allowed is None


@pytest.mark.asyncio
async def test_fake_ingestion_idempotent_rollover_and_windows():
    provider = FakeDerivativesDataProvider()
    repository = MemoryDerivativesRepository()
    session = FakeSession()
    service = DerivativesIngestionService(session, repository)
    target = date(2026, 8, 7)
    for dataset in DERIVATIVE_DATASETS:
        await service.synchronize_dataset(provider, dataset, target)
    second = await service.synchronize_dataset(provider, "FUTURES_DAILY", target)
    assert second.inserted_count == 0 and second.updated_count == 0
    assert {x.code for x in await repository.products()} == {"TX", "MTX", "TMF", "TE", "TF"}
    contracts = await repository.contracts("TX")
    assert len(contracts) == 2 and contracts[0].contract_month == "202608"
    positions = await FuturesService(repository).positions("TX", 1)
    assert len(positions) == 3


@pytest.mark.asyncio
async def test_continuous_all_roll_methods_and_boundary():
    provider = FakeDerivativesDataProvider()
    rows = []
    current = date(2026, 8, 28)
    for _ in range(25):
        if current.weekday() < 5:
            rows.extend(await provider.get_futures_daily(current))
        current += timedelta(days=1)
    tx = [x for x in rows if x.product_code == "TX"]
    for method in RollMethod:
        result = ContinuousFuturesService().build(tx, method)
        assert result and all(x["roll_method"] == method.value for x in result)


def test_validation_basis_max_pain_tie_and_missing():
    provider = FakeDerivativesDataProvider()
    import asyncio

    daily = asyncio.run(provider.get_futures_daily(date(2026, 8, 7)))[0]
    assert derivative_error(daily) is None
    meta = daily.metadata
    rows = [
        OptionStrikeOpenInterest(
            "TXO", "202608", date(2026, 8, 7), kind, Decimal(strike), 100, 1, None, meta
        )
        for strike in (21900, 22100)
        for kind in OptionType
    ]
    result = OptionMaxPainService().calculate(rows)
    assert result["derived"] and len(result["ties"]) == 2
    assert OptionMaxPainService().calculate([])["data_status"] == "UNAVAILABLE"


@pytest.mark.asyncio
async def test_official_taifex_mapping_and_schema_guard():
    payloads = {
        "/v1/DailyMarketReportFut": [
            {
                "Date": "20260807",
                "Contract": "TX",
                "ContractMonth(Week)": "202608",
                "Open": "22000",
                "High": "22100",
                "Low": "21900",
                "Last": "22050",
                "Change": "50",
                "%": "0.23%",
                "Volume": "1000",
                "SettlementPrice": "22040",
                "OpenInterest": "80000",
                "TradingSession": "一般",
            }
        ],
        "/v1/PutCallRatio": [
            {
                "Date": "20260807",
                "PutVolume": "100",
                "CallVolume": "80",
                "PutCallVolumeRatio%": "125.00",
                "PutOI": "60",
                "CallOI": "50",
                "PutCallOIRatio%": "120.00",
            }
        ],
    }

    inst_csv = (
        "\ufeff日期,商品名稱,身份別,多方交易口數,多方交易契約金額(千元),空方交易口數,空方交易契約金額(千元),多空交易口數淨額,多空交易契約金額淨額(千元),多方未平倉口數,多方未平倉契約金額(千元),空方未平倉口數,空方未平倉契約金額(千元),多空未平倉口數淨額,多空未平倉契約金額淨額(千元)\r\n"
        "20260807,臺股期貨,外資及陸資,10,100,12,120,-2,-20,32,320,95,950,-63,-630\r\n"
    )

    conc_csv = (
        "\ufeff日期,契約,商品名稱(契約名稱),到期月份(週別),交易人類別,前五大交易人買方數量,前五大交易人賣方數量,前十大交易人買方數量,前十大交易人賣方數量,全市場未沖銷部位數\r\n"
        "20260807,TX,臺股期貨,202608,0,34000,28000,37000,39000,57000\r\n"
        "20260807,TX,臺股期貨,202608,1,34000,28000,36000,39000,57000\r\n"
    )

    def handler(request):
        if request.url.path == "/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate":
            return httpx.Response(200, content=inst_csv.encode("utf-8-sig"), headers={"content-type": "application/octet-stream"})
        if request.url.path == "/v1/OpenInterestOfLargeTradersFutures":
            return httpx.Response(200, content=conc_csv.encode("utf-8-sig"), headers={"content-type": "application/octet-stream"})
        return httpx.Response(200, json=payloads.get(request.url.path, []))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OfficialTaifexProvider(transport=OfficialJsonClient(client, min_interval=0))
    assert (await provider.get_futures_daily(date(2026, 8, 7)))[0].close == Decimal("22050")
    assert (await provider.get_put_call_ratio(date(2026, 8, 7)))[0].oi_put_call_ratio == Decimal(
        "120.00"
    )
    inst = await provider.get_futures_institutional_positions(date(2026, 8, 7))
    assert len(inst) == 1
    assert inst[0].product_code == "TX"
    assert inst[0].net_oi == -63
    assert inst[0].long_oi_amount == Decimal("320000")

    conc = await provider.get_trader_concentration(date(2026, 8, 7))
    assert len(conc) == 4  # top5 buy/sell, top10 buy/sell
    top5_long = next(c for c in conc if c.top_n == 5 and c.side.value == "LONG")
    assert top5_long.open_interest == 34000
    assert top5_long.specific_institution_oi == 34000
    assert top5_long.market_open_interest == 57000

    # Non-matching date returns empty list (PARTIAL)
    assert await provider.get_futures_institutional_positions(date(2026, 8, 8)) == []
    assert await provider.get_trader_concentration(date(2026, 8, 8)) == []

    bad = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[{"bad": 1}]))
    )
    with pytest.raises(UpstreamSchemaError):
        await OfficialJsonClient(bad, min_interval=0).get_list(
            "https://official.test/data", {"Date"}
        )
    await client.aclose()
    await bad.aclose()


@pytest.mark.asyncio
async def test_official_json_client_robustness():
    # 1. Empty body returns empty list / dict
    empty_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=b"", headers={"content-type": "application/json"}))
    )
    http = OfficialJsonClient(empty_client, min_interval=0)
    assert await http.get_list("https://official.test/list", {"Date"}) == []
    assert await http.get_object("https://official.test/obj", {"Date"}) == {}
    assert await http.get_csv_list("https://official.test/csv", {"Date"}) == []
    await empty_client.aclose()

    # 2. Non-JSON (e.g. CSV with UTF-8 BOM) raises UpstreamSchemaError in get_list but succeeds in get_csv_list
    csv_bytes = "\ufeff日期,商品名稱\r\n20260817,臺股期貨".encode("utf-8-sig")
    csv_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content=csv_bytes, headers={"content-type": "application/octet-stream"}))
    )
    http = OfficialJsonClient(csv_client, min_interval=0)
    with pytest.raises(UpstreamSchemaError) as exc_info:
        await http.get_list("https://openapi.taifex.com.tw/v1/MarketData", {"Date"})
    assert "status=200" in str(exc_info.value)
    assert "content_type=application/octet-stream" in str(exc_info.value)

    # get_csv_list parses it correctly
    csv_data = await http.get_csv_list("https://openapi.taifex.com.tw/v1/MarketData", {"日期", "商品名稱"})
    assert len(csv_data) == 1
    assert csv_data[0]["日期"] == "20260817"
    assert csv_data[0]["商品名稱"] == "臺股期貨"
    await csv_client.aclose()

    # 3. CSV missing required headers raises UpstreamSchemaError
    bad_csv = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, content="\ufeffcolA,colB\r\n1,2".encode("utf-8-sig")))
    )
    http_bad = OfficialJsonClient(bad_csv, min_interval=0)
    with pytest.raises(UpstreamSchemaError) as exc_info:
        await http_bad.get_csv_list("https://official.test/bad", {"日期"})
    assert "missing required fields" in str(exc_info.value)
    await bad_csv.aclose()

    # 4. HTML / WAF error response raises UpstreamSchemaError in get_list
    html_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, text="<html><body>Error</body></html>", headers={"content-type": "text/html"}))
    )
    http = OfficialJsonClient(html_client, min_interval=0)
    with pytest.raises(UpstreamSchemaError) as exc_info:
        await http.get_list("https://openapi.taifex.com.tw/v1/Waf", {"Date"})
    assert "text/html" in str(exc_info.value)
    await html_client.aclose()

    # 5. HTTP error raises HTTPStatusError
    error_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Error"))
    )
    http = OfficialJsonClient(error_client, min_interval=0, attempts=1)
    with pytest.raises(httpx.HTTPStatusError):
        await http.get_list("https://official.test/error", {"Date"})
    await error_client.aclose()
