from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest

from app.adapters.fake_derivatives import FakeDerivativesDataProvider
from app.adapters.official_http import OfficialJsonClient, UpstreamSchemaError
from app.adapters.taifex.provider import OfficialTaifexProvider
from app.domain.derivatives import OptionStrikeOpenInterest, OptionType, RollMethod
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
        "/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate": [
            {
                "Date": "20260807",
                "ContractCode": "臺股期貨",
                "Item": "外資",
                "TradingVolume(Long)": "10",
                "TradingValue(Long)(Thousands)": "100",
                "TradingVolume(Short)": "12",
                "TradingValue(Short)(Thousands)": "120",
                "TradingVolume(Net)": "-2",
                "TradingValue(Net)(Thousands)": "-20",
                "OpenInterest(Long)": "32",
                "ContractValueofOpenInterest(Long)(Thousands)": "320",
                "OpenInterest(Short)": "95",
                "ContractValueofOpenInterest(Short)(Thousands)": "950",
                "OpenInterest(Net)": "-63",
                "ContractValueofOpenInterest(Net)(Thousands)": "-630",
            }
        ],
    }

    def handler(request):
        return httpx.Response(200, json=payloads.get(request.url.path, []))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OfficialTaifexProvider(transport=OfficialJsonClient(client, min_interval=0))
    assert (await provider.get_futures_daily(date(2026, 8, 7)))[0].close == Decimal("22050")
    assert (await provider.get_put_call_ratio(date(2026, 8, 7)))[0].oi_put_call_ratio == Decimal(
        "120.00"
    )
    assert (await provider.get_futures_institutional_positions(date(2026, 8, 7)))[0].net_oi == -63
    bad = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[{"bad": 1}]))
    )
    with pytest.raises(UpstreamSchemaError):
        await OfficialJsonClient(bad, min_interval=0).get_list(
            "https://official.test/data", {"Date"}
        )
    await client.aclose()
    await bad.aclose()
