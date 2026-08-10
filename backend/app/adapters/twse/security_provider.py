from datetime import UTC, date, datetime

import httpx

from app.adapters.daily_price_mapping import RawPriceRow, make_daily_price
from app.adapters.market_spot_mapping import map_index, map_lending, map_margin
from app.adapters.security_mapping import RawRow, make_record
from app.domain.pricing import DailyPriceRecord, SecurityKey
from app.domain.security import MarketCode, SecurityRecord


class TwseSecurityProvider:
    source_code = "TWSE"
    endpoint = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    daily_endpoint = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    def map_row(
        self, row: RawRow, *, as_of: datetime, received_at: datetime
    ) -> SecurityRecord | None:
        return make_record(
            market=MarketCode.TWSE,
            code=str(row.get("公司代號", "")),
            name=str(row.get("公司簡稱", "")),
            industry_code=str(row.get("產業別", "")) or None,
            industry_name=str(row.get("產業別名稱", "")) or None,
            listing_date=str(row.get("上市日期", "")) or None,
            source_code=self.source_code,
            as_of=as_of,
            received_at=received_at,
        )

    async def list_securities(self) -> list[SecurityRecord]:
        received_at = datetime.now(UTC)
        client = self.client or httpx.AsyncClient(timeout=30)
        close = self.client is None
        try:
            response = await client.get(self.endpoint)
            response.raise_for_status()
            as_of = received_at
            return [
                record
                for row in response.json()
                if (record := self.map_row(row, as_of=as_of, received_at=received_at))
            ]
        finally:
            if close:
                await client.aclose()

    def map_daily_row(
        self, row: RawPriceRow, *, trade_date: date, received_at: datetime
    ) -> DailyPriceRecord | None:
        return make_daily_price(
            market=MarketCode.TWSE,
            code=row.get("證券代號", row.get("Code", "")),
            trade_date=row.get("日期", trade_date.isoformat()),
            fallback_date=trade_date,
            open_=row.get("開盤價", row.get("OpeningPrice", "")),
            high=row.get("最高價", row.get("HighestPrice", "")),
            low=row.get("最低價", row.get("LowestPrice", "")),
            close=row.get("收盤價", row.get("ClosingPrice", "")),
            volume=row.get("成交股數", row.get("TradeVolume", "")),
            turnover=row.get("成交金額", row.get("TradeValue", "")),
            source_code="TWSE_DAILY",
            received_at=received_at,
        )

    def map_index_row(self, row, *, trade_date: date, received_at: datetime):
        return map_index(
            row,
            market=MarketCode.TWSE,
            code="TAIEX",
            name="加權指數",
            trade_date=trade_date,
            received_at=received_at,
            source="TWSE_MI_INDEX",
            keys={
                "open": "開盤指數",
                "high": "最高指數",
                "low": "最低指數",
                "close": "收盤指數",
                "change": "漲跌點數",
                "change_percent": "漲跌百分比",
                "turnover": "成交金額",
                "volume": "成交筆數",
            },
        )

    def map_margin_row(self, row, *, trade_date: date, received_at: datetime):
        code = str(row.get("股票代號", "")) or None
        return map_margin(
            row,
            market=MarketCode.TWSE,
            trade_date=trade_date,
            received_at=received_at,
            source="TWSE_MARGIN",
            keys={
                "margin_buy": "融資買進",
                "margin_sell": "融資賣出",
                "margin_cash_repayment": "現金償還",
                "margin_balance": "融資今日餘額",
                "short_sell": "融券賣出",
                "short_cover": "融券買進",
                "short_stock_repayment": "現券償還",
                "short_balance": "融券今日餘額",
                "short_margin_ratio": "券資比",
            },
            security_code=code,
        )

    def map_lending_row(self, row, *, trade_date: date, received_at: datetime):
        code = str(row.get("股票代號", "")) or None
        return map_lending(
            row,
            market=MarketCode.TWSE,
            trade_date=trade_date,
            received_at=received_at,
            source="TWSE_LENDING",
            keys={
                "lending_sell": "借券賣出",
                "lending_return": "借券還券",
                "lending_balance": "借券餘額",
                "lending_balance_change": "借券餘額異動",
            },
            security_code=code,
        )

    async def get_daily_prices(
        self,
        trade_date: date | None = None,
        security: SecurityKey | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceRecord]:
        del start_date, end_date
        target = trade_date or date.today()
        client = self.client or httpx.AsyncClient(timeout=30)
        close = self.client is None
        try:
            response = await client.get(
                self.daily_endpoint,
                params={
                    "date": target.strftime("%Y%m%d"),
                    "type": "ALLBUT0999",
                    "response": "json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            tables = payload.get("tables", [])
            rows = next(
                (
                    table.get("data", [])
                    for table in tables
                    if "每日收盤行情" in table.get("title", "")
                ),
                [],
            )
            fields = next(
                (
                    table.get("fields", [])
                    for table in tables
                    if "每日收盤行情" in table.get("title", "")
                ),
                [],
            )
            mapped = [
                self.map_daily_row(
                    dict(zip(fields, row, strict=False)),
                    trade_date=target,
                    received_at=datetime.now(UTC),
                )
                for row in rows
            ]
            return [
                item
                for item in mapped
                if item is not None and (security is None or item.security == security)
            ]
        finally:
            if close:
                await client.aclose()
