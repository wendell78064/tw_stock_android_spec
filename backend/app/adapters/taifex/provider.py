from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.adapters.fake_derivatives import PRODUCTS, third_wednesday
from app.adapters.official_http import OfficialJsonClient
from app.domain.derivatives import (
    TAIWAN_VIX_POLICY,
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
    VixSourceCapability,
    VolatilityIndex,
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
    "小型臺指期貨": "MTX",
    "微型臺指": "TMF",
    "微型臺指期貨": "TMF",
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
    return datetime.strptime(value.replace("/", "").replace("-", ""), "%Y%m%d").date()


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
        raw_code = str(row.get("商品名稱") or row.get("ContractCode", "")).strip()
        product = PRODUCT_NAMES.get(raw_code)
        raw_inst = str(row.get("身份別") or row.get("Item", "")).strip()
        institution = INSTITUTIONS.get(raw_inst)
        if not product or not institution:
            return None
        raw_date = str(row.get("日期") or row.get("Date", "")).strip()
        target = parse_date(raw_date)
        return InstitutionFuturesPosition(
            product,
            target,
            institution,
            integer(row.get("多方交易口數") or row.get("TradingVolume(Long)")),
            integer(row.get("空方交易口數") or row.get("TradingVolume(Short)")),
            integer(row.get("多空交易口數淨額") or row.get("TradingVolume(Net)")),
            thousands(
                row.get("多方交易契約金額(千元)") or row.get("TradingValue(Long)(Thousands)")
            ),
            thousands(
                row.get("空方交易契約金額(千元)") or row.get("TradingValue(Short)(Thousands)")
            ),
            thousands(
                row.get("多空交易契約金額淨額(千元)") or row.get("TradingValue(Net)(Thousands)")
            ),
            integer(row.get("多方未平倉口數") or row.get("OpenInterest(Long)")),
            integer(row.get("空方未平倉口數") or row.get("OpenInterest(Short)")),
            integer(row.get("多空未平倉口數淨額") or row.get("OpenInterest(Net)")),
            thousands(
                row.get("多方未平倉契約金額(千元)")
                or row.get("ContractValueofOpenInterest(Long)(Thousands)")
            ),
            thousands(
                row.get("空方未平倉契約金額(千元)")
                or row.get("ContractValueofOpenInterest(Short)(Thousands)")
            ),
            thousands(
                row.get("多空未平倉契約金額淨額(千元)")
                or row.get("ContractValueofOpenInterest(Net)(Thousands)")
            ),
            meta(target, received_at, "INSTITUTION_FUTURES"),
        )

    async def get_futures_institutional_positions(
        self, trade_date: date
    ) -> list[InstitutionFuturesPosition]:
        rows = await self.http.get_csv_list(
            TAIFEX_ENDPOINTS["institutional"], {"日期", "商品名稱", "身份別"}
        )
        now = datetime.now(UTC)
        return [
            mapped
            for row in rows
            if (row.get("日期") or row.get("Date")) == trade_date.strftime("%Y%m%d")
            and (mapped := self.map_position(row, now))
        ]

    async def get_trader_concentration(self, trade_date: date) -> list[TraderConcentration]:
        rows = await self.http.get_csv_list(
            TAIFEX_ENDPOINTS["concentration"],
            {"日期", "契約", "到期月份(週別)"},
        )
        now = datetime.now(UTC)
        target_str = trade_date.strftime("%Y%m%d")
        by_scope = {}
        for row in rows:
            if (row.get("日期") or row.get("Date")) != target_str:
                continue
            contract = str(row.get("契約") or row.get("Contract", "")).strip()
            if contract not in {p[0] for p in PRODUCTS}:
                continue
            scope = str(row.get("到期月份(週別)") or row.get("SettlementMonth", "ALL")).strip()
            trader_type = str(row.get("交易人類別") or "").strip()
            by_scope.setdefault((contract, scope), {})[trader_type] = row

        result = []
        for (product, scope), types in by_scope.items():
            all_traders = types.get("0") or types.get("ALL") or types.get("")
            spec_traders = types.get("1")
            if not all_traders:
                continue
            market_oi = integer(
                all_traders.get("全市場未沖銷部位數") or all_traders.get("OIOfMarket")
            )
            for top_n, num_str in [(5, "五"), (10, "十")]:
                for side, suffix, en_suffix in [
                    (PositionSide.LONG, "買方數量", "Buy"),
                    (PositionSide.SHORT, "賣方數量", "Sell"),
                ]:
                    col_zh = f"前{num_str}大交易人{suffix}"
                    col_en = f"Top{top_n}{en_suffix}"
                    oi = integer(all_traders.get(col_zh) or all_traders.get(col_en))
                    spec_oi = (
                        integer(spec_traders.get(col_zh) or spec_traders.get(col_en))
                        if spec_traders
                        else None
                    )
                    ratio = (
                        Decimal(oi) / Decimal(market_oi) * 100
                        if oi is not None and market_oi
                        else None
                    )
                    result.append(
                        TraderConcentration(
                            product,
                            trade_date,
                            scope,
                            side,
                            top_n,
                            oi,
                            market_oi,
                            ratio,
                            spec_oi,
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
