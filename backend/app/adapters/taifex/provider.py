from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.adapters.fake_derivatives import PRODUCTS, third_wednesday
from app.adapters.official_http import OfficialJsonClient
from app.domain.derivatives import (
    ContractStatus,
    FuturesContract,
    FuturesDailyPrice,
    FuturesProduct,
    InstitutionFuturesPosition,
    OptionPutCallRatio,
    OptionStrikeOpenInterest,
    OptionType,
    PositionSide,
    SessionType,
    TraderConcentration,
    VolatilityIndex,
    TAIWAN_VIX_POLICY,
    VixSourceCapability,
)
from app.domain.market_data import DataStatus
from app.domain.market_spot import InstitutionType, SourceMetadata

TAIFEX_BASE = "https://openapi.taifex.com.tw/v1"
TAIFEX_ENDPOINTS = {
    "futures_daily": f"{TAIFEX_BASE}/DailyMarketReportFut",
    "institutional": (
        f"{TAIFEX_BASE}/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate"
    ),
    "concentration": f"{TAIFEX_BASE}/OpenInterestOfLargeTradersFutures",
    "put_call": f"{TAIFEX_BASE}/PutCallRatio",
    "option_daily": f"{TAIFEX_BASE}/DailyMarketReportOpt",
}

PRODUCT_NAMES = {
    "臺股期貨": "TX",
    "小型臺指": "MTX",
    "微型臺指": "TMF",
    "電子期貨": "TE",
    "金融期貨": "TF",
}
INSTITUTIONS = {
    "外資": InstitutionType.FOREIGN,
    "外資及陸資": InstitutionType.FOREIGN,
    "投信": InstitutionType.INVESTMENT_TRUST,
    "自營商": InstitutionType.DEALER,
}


def number(value) -> Decimal | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except InvalidOperation:
        return None


def integer(value) -> int | None:
    parsed = number(value)
    return int(parsed) if parsed is not None else None


def thousands(value) -> Decimal | None:
    parsed = number(value)
    return parsed * Decimal(1000) if parsed is not None else None


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def meta(target: date, received_at: datetime, dataset: str) -> SourceMetadata:
    return SourceMetadata(
        f"TAIFEX_{dataset}",
        datetime(target.year, target.month, target.day, tzinfo=UTC),
        received_at,
        DataStatus.FINAL,
        "oas-v1",
    )


class OfficialTaifexProvider:
    source_code = "TAIFEX"
    vix_source_capability = VixSourceCapability.OFFICIAL_DOWNLOAD
    vix_policy = TAIWAN_VIX_POLICY

    def __init__(
        self, client: httpx.AsyncClient | None = None, transport: OfficialJsonClient | None = None
    ):
        self.http = transport or OfficialJsonClient(client)

    async def get_futures_products(self) -> list[FuturesProduct]:
        return [
            FuturesProduct(code, name, Decimal(multiplier), "TWD", SessionType.COMBINED)
            for code, name, multiplier in PRODUCTS
        ]

    async def get_futures_contracts(self, trade_date: date) -> list[FuturesContract]:
        daily = await self.get_futures_daily(trade_date)
        return [
            FuturesContract(
                row.product_code,
                row.contract_code,
                row.contract_month,
                third_wednesday(int(row.contract_month[:4]), int(row.contract_month[4:6])),
                third_wednesday(int(row.contract_month[:4]), int(row.contract_month[4:6])),
                ContractStatus.ACTIVE,
                True,
            )
            for row in daily
        ]

    def map_futures(self, row: dict, received_at: datetime) -> FuturesDailyPrice | None:
        product = str(row.get("Contract", "")).strip()
        month = str(row.get("ContractMonth(Week)", "")).strip()
        if product not in {p[0] for p in PRODUCTS} or len(month) != 6 or not month.isdigit():
            return None
        target = parse_date(row["Date"])
        session = (
            SessionType.AFTER_HOURS
            if "盤後" in row.get("TradingSession", "")
            else SessionType.REGULAR
        )
        return FuturesDailyPrice(
            product,
            f"{product}{month}",
            month,
            target,
            session,
            number(row.get("Open")),
            number(row.get("High")),
            number(row.get("Low")),
            number(row.get("Last")),
            number(row.get("SettlementPrice")),
            number(row.get("Change")),
            number(row.get("%")),
            integer(row.get("Volume")),
            integer(row.get("OpenInterest")),
            meta(target, received_at, "DAILY_FUTURES"),
        )

    async def get_futures_daily(self, trade_date: date) -> list[FuturesDailyPrice]:
        rows = await self.http.get_list(
            TAIFEX_ENDPOINTS["futures_daily"], {"Date", "Contract", "ContractMonth(Week)"}
        )
        now = datetime.now(UTC)
        return [
            mapped
            for row in rows
            if row.get("Date") == trade_date.strftime("%Y%m%d")
            and (mapped := self.map_futures(row, now))
        ]

    def map_position(self, row: dict, received_at: datetime) -> InstitutionFuturesPosition | None:
        product = PRODUCT_NAMES.get(str(row.get("ContractCode", "")).strip())
        institution = INSTITUTIONS.get(str(row.get("Item", "")).strip())
        if not product or not institution:
            return None
        target = parse_date(row["Date"])
        return InstitutionFuturesPosition(
            product,
            target,
            institution,
            integer(row.get("TradingVolume(Long)")),
            integer(row.get("TradingVolume(Short)")),
            integer(row.get("TradingVolume(Net)")),
            thousands(row.get("TradingValue(Long)(Thousands)")),
            thousands(row.get("TradingValue(Short)(Thousands)")),
            thousands(row.get("TradingValue(Net)(Thousands)")),
            integer(row.get("OpenInterest(Long)")),
            integer(row.get("OpenInterest(Short)")),
            integer(row.get("OpenInterest(Net)")),
            thousands(row.get("ContractValueofOpenInterest(Long)(Thousands)")),
            thousands(row.get("ContractValueofOpenInterest(Short)(Thousands)")),
            thousands(row.get("ContractValueofOpenInterest(Net)(Thousands)")),
            meta(target, received_at, "INSTITUTION_FUTURES"),
        )

    async def get_futures_institutional_positions(
        self, trade_date: date
    ) -> list[InstitutionFuturesPosition]:
        rows = await self.http.get_list(
            TAIFEX_ENDPOINTS["institutional"], {"Date", "ContractCode", "Item"}
        )
        now = datetime.now(UTC)
        return [
            mapped
            for row in rows
            if row.get("Date") == trade_date.strftime("%Y%m%d")
            and (mapped := self.map_position(row, now))
        ]

    async def get_trader_concentration(self, trade_date: date) -> list[TraderConcentration]:
        rows = await self.http.get_list(
            TAIFEX_ENDPOINTS["concentration"],
            {"Date", "Contract", "Top5Buy", "Top5Sell", "OIOfMarket"},
        )
        now = datetime.now(UTC)
        result = []
        for row in rows:
            product = row.get("Contract")
            market_oi = integer(row.get("OIOfMarket"))
            if row.get("Date") != trade_date.strftime("%Y%m%d") or product not in {
                p[0] for p in PRODUCTS
            }:
                continue
            for top_n in (5, 10):
                for side, suffix in ((PositionSide.LONG, "Buy"), (PositionSide.SHORT, "Sell")):
                    oi = integer(row.get(f"Top{top_n}{suffix}"))
                    ratio = (
                        Decimal(oi) / Decimal(market_oi) * 100
                        if oi is not None and market_oi
                        else None
                    )
                    result.append(
                        TraderConcentration(
                            product,
                            trade_date,
                            row.get("SettlementMonth", "ALL"),
                            side,
                            top_n,
                            oi,
                            market_oi,
                            ratio,
                            None,
                            meta(trade_date, now, "CONCENTRATION"),
                        )
                    )
        return result

    async def get_put_call_ratio(self, trade_date: date) -> list[OptionPutCallRatio]:
        rows = await self.http.get_list(
            TAIFEX_ENDPOINTS["put_call"], {"Date", "PutVolume", "CallVolume", "PutOI", "CallOI"}
        )
        now = datetime.now(UTC)
        result = []
        for row in rows:
            if row.get("Date") == trade_date.strftime("%Y%m%d"):
                result.append(
                    OptionPutCallRatio(
                        "TXO",
                        trade_date,
                        integer(row.get("PutVolume")),
                        integer(row.get("CallVolume")),
                        number(row.get("PutCallVolumeRatio%")),
                        integer(row.get("PutOI")),
                        integer(row.get("CallOI")),
                        number(row.get("PutCallOIRatio%")),
                        meta(trade_date, now, "PUT_CALL"),
                    )
                )
        return result

    async def get_option_open_interest_by_strike(
        self, trade_date: date
    ) -> list[OptionStrikeOpenInterest]:
        rows = await self.http.get_list(
            TAIFEX_ENDPOINTS["option_daily"],
            {"Date", "Contract", "ContractMonth(Week)", "StrikePrice", "CallPut"},
        )
        now = datetime.now(UTC)
        result = []
        for row in rows:
            if row.get("Date") != trade_date.strftime("%Y%m%d") or row.get("Contract") != "TXO":
                continue
            strike = number(row.get("StrikePrice"))
            if strike is None:
                continue
            result.append(
                OptionStrikeOpenInterest(
                    "TXO",
                    row["ContractMonth(Week)"],
                    trade_date,
                    OptionType.CALL if row.get("CallPut") == "買權" else OptionType.PUT,
                    strike,
                    integer(row.get("OpenInterest")),
                    integer(row.get("Volume")),
                    number(row.get("SettlementPrice")),
                    meta(trade_date, now, "OPTION_OI"),
                )
            )
        return result

    async def get_volatility_index(self, trade_date: date) -> list[VolatilityIndex]:
        # TAIWAN VIX is not exposed by TAIFEX OAS; licensed/manual sources must use this boundary.
        return []
