from datetime import UTC, date, datetime
from decimal import Decimal

import httpx

from app.adapters.market_spot_mapping import (
    decimal_value,
    integer_value,
    map_index,
    map_lending,
    map_margin,
)
from app.adapters.official_http import OfficialJsonClient
from app.domain.market_data import DataStatus
from app.domain.market_spot import (
    DealerSubtype,
    InstitutionalRecord,
    InstitutionType,
    MarginRecord,
    MarketBreadthRecord,
    MarketIndexRecord,
    SourceMetadata,
)
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode

SPOT_ENDPOINTS = {
    "TWSE": {
        "index": "https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST",
        "market": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
        "institutional_security": "https://www.twse.com.tw/rwd/zh/fund/T86",
        "institutional_market": "https://www.twse.com.tw/rwd/zh/fund/BFI82U",
        "margin": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",
    },
    "TPEX": {
        "index": "https://www.tpex.org.tw/openapi/v1/tpex_index",
        "breadth": "https://www.tpex.org.tw/openapi/v1/tpex_mainborad_highlight",
        "institutional_security": "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading",
        "institutional_market": "https://www.tpex.org.tw/openapi/v1/tpex_3insti_summary",
        "margin": "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance",
        "lending": "https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl",
    },
}


def roc(value: str) -> date:
    raw = value.replace("/", "").replace("-", "")
    if len(raw) == 7:
        return date(int(raw[:3]) + 1911, int(raw[3:5]), int(raw[5:7]))
    return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))


def spot_meta(market: str, dataset: str, target: date, received: datetime):
    return SourceMetadata(
        f"{market}_{dataset}",
        datetime(target.year, target.month, target.day, tzinfo=UTC),
        received,
        DataStatus.FINAL,
        "official-oas-v1",
    )


def common(code: str) -> bool:
    return len(code.strip()) == 4 and code.strip().isdigit()


class OfficialTwseProvider:
    source_code = "TWSE"

    def __init__(
        self, client: httpx.AsyncClient | None = None, transport: OfficialJsonClient | None = None
    ):
        self.http = transport or OfficialJsonClient(client)

    async def get_market_indexes(self, trade_date: date) -> list[MarketIndexRecord]:
        rows = await self.http.get_list(
            SPOT_ENDPOINTS["TWSE"]["index"],
            {"Date", "OpeningIndex", "HighestIndex", "LowestIndex", "ClosingIndex"},
        )
        now = datetime.now(UTC)
        return [
            map_index(
                r,
                market=MarketCode.TWSE,
                code="TAIEX",
                name="加權指數",
                trade_date=trade_date,
                received_at=now,
                source="TWSE_INDEX",
                keys={
                    "open": "OpeningIndex",
                    "high": "HighestIndex",
                    "low": "LowestIndex",
                    "close": "ClosingIndex",
                    "change": "Change",
                    "change_percent": "ChangePercent",
                    "turnover": "Turnover",
                    "volume": "Volume",
                },
            )
            for r in rows
            if roc(r["Date"]) == trade_date
        ]

    async def get_market_breadth(self, trade_date: date):
        payload = await self._rwd(
            SPOT_ENDPOINTS["TWSE"]["market"],
            trade_date,
            {"date": trade_date.strftime("%Y%m%d"), "type": "ALLBUT0999", "response": "json"},
        )
        now = datetime.now(UTC)
        values = {}
        for table in payload.get("tables", []):
            if "漲跌證券數合計" not in table.get("title", ""):
                continue
            fields = table.get("fields", [])
            stock_index = fields.index("股票") if "股票" in fields else 1
            for row in table.get("data", []):
                values[row[0]] = str(row[stock_index])

        def count(label: str) -> int | None:
            raw = values.get(label)
            return integer_value(raw.split("(", 1)[0]) if raw else None

        def nested(label: str) -> int | None:
            raw = values.get(label)
            if not raw or "(" not in raw:
                return None
            return integer_value(raw.split("(", 1)[1].rstrip(")"))

        if not values:
            return []
        advancers = count("上漲(漲停)")
        decliners = count("下跌(跌停)")
        unchanged = count("持平")
        return [
            MarketBreadthRecord(
                MarketCode.TWSE,
                trade_date,
                advancers,
                decliners,
                unchanged,
                nested("上漲(漲停)"),
                nested("下跌(跌停)"),
                sum(x for x in (advancers, decliners, unchanged) if x is not None),
                None,
                spot_meta("TWSE", "BREADTH", trade_date, now),
            )
        ]

    async def _rwd(self, endpoint, target, params):
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return await self.http.get_object(f"{endpoint}?{query}", {"stat", "date"})

    async def get_market_institutional_spot(self, trade_date: date):
        payload = await self._rwd(
            SPOT_ENDPOINTS["TWSE"]["institutional_market"],
            trade_date,
            {"dayDate": trade_date.strftime("%Y%m%d"), "type": "day", "response": "json"},
        )
        now = datetime.now(UTC)
        result = []
        mapping = {
            "外資及陸資(不含外資自營商)": (InstitutionType.FOREIGN, None),
            "投信": (InstitutionType.INVESTMENT_TRUST, None),
            "自營商(自行買賣)": (InstitutionType.DEALER, DealerSubtype.PROPRIETARY),
            "自營商(避險)": (InstitutionType.DEALER, DealerSubtype.HEDGE),
            "合計": (InstitutionType.TOTAL, None),
        }
        for values in payload.get("data", []):
            row = dict(zip(payload["fields"], values, strict=False))
            kind = mapping.get(row.get("單位名稱"))
            if kind:
                result.append(
                    InstitutionalRecord(
                        MarketCode.TWSE,
                        trade_date,
                        kind[0],
                        kind[1],
                        decimal_value(row["買進金額"]),
                        decimal_value(row["賣出金額"]),
                        decimal_value(row["買賣差額"]),
                        spot_meta("TWSE", "MARKET_INSTITUTIONAL", trade_date, now),
                    )
                )
        return result

    async def get_security_institutional_spot(self, trade_date: date):
        payload = await self._rwd(
            SPOT_ENDPOINTS["TWSE"]["institutional_security"],
            trade_date,
            {"date": trade_date.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"},
        )
        now = datetime.now(UTC)
        result = []
        for values in payload.get("data", []):
            row = dict(zip(payload["fields"], values, strict=False))
            code = row.get("證券代號", "").strip()
            if not common(code):
                continue
            for institution, subtype, buy, sell, net in (
                (
                    InstitutionType.FOREIGN,
                    None,
                    "外陸資買進股數(不含外資自營商)",
                    "外陸資賣出股數(不含外資自營商)",
                    "外陸資買賣超股數(不含外資自營商)",
                ),
                (
                    InstitutionType.INVESTMENT_TRUST,
                    None,
                    "投信買進股數",
                    "投信賣出股數",
                    "投信買賣超股數",
                ),
                (
                    InstitutionType.DEALER,
                    DealerSubtype.PROPRIETARY,
                    "自營商買進股數(自行買賣)",
                    "自營商賣出股數(自行買賣)",
                    "自營商買賣超股數(自行買賣)",
                ),
                (
                    InstitutionType.DEALER,
                    DealerSubtype.HEDGE,
                    "自營商買進股數(避險)",
                    "自營商賣出股數(避險)",
                    "自營商買賣超股數(避險)",
                ),
            ):
                result.append(
                    InstitutionalRecord(
                        MarketCode.TWSE,
                        trade_date,
                        institution,
                        subtype,
                        integer_value(row.get(buy)),
                        integer_value(row.get(sell)),
                        integer_value(row.get(net)),
                        spot_meta("TWSE", "SECURITY_INSTITUTIONAL", trade_date, now),
                        SecurityKey(MarketCode.TWSE, code),
                        False,
                    )
                )
        return result

    async def get_security_margin_trading(self, trade_date: date):
        payload = await self._rwd(
            SPOT_ENDPOINTS["TWSE"]["margin"],
            trade_date,
            {"date": trade_date.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"},
        )
        now = datetime.now(UTC)
        rows = []
        for table in payload.get("tables", []):
            if "融資融券彙總" not in table.get("title", ""):
                continue
            for values in table.get("data", []):
                code = values[0].strip()
                if common(code):
                    margin_previous = integer_value(values[5], 1000)
                    margin_balance = integer_value(values[6], 1000)
                    short_previous = integer_value(values[11], 1000)
                    short_balance = integer_value(values[12], 1000)
                    rows.append(
                        MarginRecord(
                            MarketCode.TWSE,
                            trade_date,
                            integer_value(values[2], 1000),
                            integer_value(values[3], 1000),
                            integer_value(values[4], 1000),
                            margin_balance,
                            margin_balance - margin_previous
                            if margin_balance is not None and margin_previous is not None
                            else None,
                            integer_value(values[9], 1000),
                            integer_value(values[8], 1000),
                            integer_value(values[10], 1000),
                            short_balance,
                            short_balance - short_previous
                            if short_balance is not None and short_previous is not None
                            else None,
                            None,
                            spot_meta("TWSE", "MARGIN", trade_date, now),
                            SecurityKey(MarketCode.TWSE, code),
                        )
                    )
        return rows

    async def get_market_margin_trading(self, trade_date: date):
        payload = await self._rwd(
            SPOT_ENDPOINTS["TWSE"]["margin"],
            trade_date,
            {"date": trade_date.strftime("%Y%m%d"), "selectType": "ALL", "response": "json"},
        )
        now = datetime.now(UTC)
        values = {}
        for table in payload.get("tables", []):
            if "信用交易統計" in table.get("title", ""):
                values = {row[0]: row for row in table.get("data", [])}
        margin = values.get("融資(交易單位)")
        short = values.get("融券(交易單位)")
        if not margin or not short:
            return []
        margin_previous, margin_balance = integer_value(margin[4], 1000), integer_value(
            margin[5], 1000
        )
        short_previous, short_balance = integer_value(short[4], 1000), integer_value(
            short[5], 1000
        )
        return [
            MarginRecord(
                MarketCode.TWSE,
                trade_date,
                integer_value(margin[1], 1000),
                integer_value(margin[2], 1000),
                integer_value(margin[3], 1000),
                margin_balance,
                margin_balance - margin_previous,
                integer_value(short[2], 1000),
                integer_value(short[1], 1000),
                integer_value(short[3], 1000),
                short_balance,
                short_balance - short_previous,
                None,
                spot_meta("TWSE", "MARKET_MARGIN", trade_date, now),
            )
        ]

    async def get_market_securities_lending(self, trade_date: date):
        return []

    async def get_security_securities_lending(self, trade_date: date):
        return []


class OfficialTpexProvider:
    source_code = "TPEX"

    def __init__(
        self, client: httpx.AsyncClient | None = None, transport: OfficialJsonClient | None = None
    ):
        self.http = transport or OfficialJsonClient(client)

    async def _rows(self, key, required):
        return await self.http.get_list(SPOT_ENDPOINTS["TPEX"][key], required)

    async def get_market_indexes(self, trade_date):
        rows = await self._rows("index", {"Date", "Open", "High", "Low", "Close"})
        now = datetime.now(UTC)
        return [
            map_index(
                r,
                market=MarketCode.TPEX,
                code="OTC",
                name="櫃買指數",
                trade_date=trade_date,
                received_at=now,
                source="TPEX_INDEX",
                keys={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "change": "Change",
                    "change_percent": "ChangePercent",
                    "turnover": "TransactionAmount",
                    "volume": "TransactionCount",
                },
            )
            for r in rows
            if roc(r["Date"]) == trade_date
        ]

    async def get_market_breadth(self, trade_date):
        rows = await self._rows(
            "breadth",
            {
                "Date",
                "PriceRiseCompanyNumbers",
                "PriceDeclineCompanyNumbers",
                "PriceFlatCompanyNumbers",
            },
        )
        now = datetime.now(UTC)
        return [
            MarketBreadthRecord(
                MarketCode.TPEX,
                trade_date,
                integer_value(r.get("PriceRiseCompanyNumbers")),
                integer_value(r.get("PriceDeclineCompanyNumbers")),
                integer_value(r.get("PriceFlatCompanyNumbers")),
                integer_value(r.get("LimitUpCompanyNumbers")),
                integer_value(r.get("LimitDownCompanyNumbers")),
                None,
                decimal_value(r.get("DailyTradingValue")) * Decimal(1000),
                spot_meta("TPEX", "BREADTH", trade_date, now),
            )
            for r in rows
            if roc(r["Date"]) == trade_date
        ]

    async def get_market_institutional_spot(self, trade_date):
        rows = await self._rows(
            "institutional_market", {"Date", "Investor", "PurchaseAmount", "SaleAmount", "Net"}
        )
        now = datetime.now(UTC)
        mapping = {
            "外資及陸資合計": InstitutionType.FOREIGN,
            "投信": InstitutionType.INVESTMENT_TRUST,
            "自營商合計": InstitutionType.DEALER,
            "合計": InstitutionType.TOTAL,
        }
        return [
            InstitutionalRecord(
                MarketCode.TPEX,
                trade_date,
                mapping[r["Investor"]],
                None,
                decimal_value(r["PurchaseAmount"]),
                decimal_value(r["SaleAmount"]),
                decimal_value(r["Net"]),
                spot_meta("TPEX", "MARKET_INSTITUTIONAL", trade_date, now),
            )
            for r in rows
            if roc(r["Date"]) == trade_date and r.get("Investor") in mapping
        ]

    async def get_security_institutional_spot(self, trade_date):
        rows = await self._rows("institutional_security", {"Date", "SecuritiesCompanyCode"})
        now = datetime.now(UTC)
        result = []
        foreign_prefix = (
            "Foreign Investors include Mainland Area Investors (Foreign Dealers excluded)"
        )
        for r in rows:
            code = r["SecuritiesCompanyCode"].strip()
            if roc(r["Date"]) != trade_date or not common(code):
                continue
            for institution, buy, sell, net in (
                (
                    InstitutionType.FOREIGN,
                    f"{foreign_prefix}-Total Buy",
                    f" {foreign_prefix}-Total Sell",
                    f"{foreign_prefix}-Difference",
                ),
                (
                    InstitutionType.INVESTMENT_TRUST,
                    "SecuritiesInvestmentTrustCompanies-TotalBuy",
                    "SecuritiesInvestmentTrustCompanies-TotalSell",
                    "SecuritiesInvestmentTrustCompanies-Difference",
                ),
                (
                    InstitutionType.DEALER,
                    "Dealers-TotalBuy",
                    "Dealers-TotalSell",
                    "Dealers-Difference",
                ),
            ):
                result.append(
                    InstitutionalRecord(
                        MarketCode.TPEX,
                        trade_date,
                        institution,
                        None,
                        integer_value(r.get(buy)),
                        integer_value(r.get(sell)),
                        integer_value(r.get(net)),
                        spot_meta("TPEX", "SECURITY_INSTITUTIONAL", trade_date, now),
                        SecurityKey(MarketCode.TPEX, code),
                        False,
                    )
                )
        return result

    async def get_security_margin_trading(self, trade_date):
        rows = await self._rows(
            "margin", {"Date", "SecuritiesCompanyCode", "MarginPurchaseBalance", "ShortSaleBalance"}
        )
        now = datetime.now(UTC)
        return [
            map_margin(
                r,
                market=MarketCode.TPEX,
                trade_date=trade_date,
                received_at=now,
                source="TPEX_MARGIN",
                keys={
                    "margin_buy": "MarginPurchase",
                    "margin_sell": "MarginSales",
                    "margin_cash_repayment": "CashRedemption",
                    "margin_balance": "MarginPurchaseBalance",
                    "short_sell": "ShortSale",
                    "short_cover": "ShortConvering",
                    "short_stock_repayment": "StockRedemption",
                    "short_balance": "ShortSaleBalance",
                },
                security_code=r["SecuritiesCompanyCode"].strip(),
            )
            for r in rows
            if roc(r["Date"]) == trade_date and common(r["SecuritiesCompanyCode"])
        ]

    async def get_security_securities_lending(self, trade_date):
        rows = await self._rows(
            "lending", {"Date", "SecuritiesCompanyCode", "SecuritiesBorrowingBalanceOfTheMarketDay"}
        )
        now = datetime.now(UTC)
        return [
            map_lending(
                r,
                market=MarketCode.TPEX,
                trade_date=trade_date,
                received_at=now,
                source="TPEX_LENDING",
                keys={
                    "lending_sell": "SecuritiesBorrowingSale",
                    "lending_return": "SecuritiesBorrowingReturn",
                    "lending_balance": "SecuritiesBorrowingBalanceOfTheMarketDay",
                    "lending_balance_change": "SecuritiesBorrowingAdjustment",
                },
                security_code=r["SecuritiesCompanyCode"].strip(),
            )
            for r in rows
            if roc(r["Date"]) == trade_date and common(r["SecuritiesCompanyCode"])
        ]

    async def get_market_margin_trading(self, trade_date):
        return []

    async def get_market_securities_lending(self, trade_date):
        return []
