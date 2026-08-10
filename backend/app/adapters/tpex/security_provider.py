from datetime import UTC, date, datetime

import httpx

from app.adapters.daily_price_mapping import RawPriceRow, make_daily_price
from app.adapters.market_spot_mapping import map_index, map_lending, map_margin
from app.adapters.security_mapping import RawRow, make_record
from app.domain.pricing import DailyPriceRecord, SecurityKey
from app.domain.security import MarketCode, SecurityRecord


class TpexSecurityProvider:
    source_code = "TPEX"
    endpoint = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
    daily_endpoint = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    def map_row(
        self, row: RawRow, *, as_of: datetime, received_at: datetime
    ) -> SecurityRecord | None:
        return make_record(
            market=MarketCode.TPEX,
            code=str(row.get("SecuritiesCompanyCode", row.get("公司代號", ""))),
            name=str(row.get("CompanyAbbreviation", row.get("公司簡稱", ""))),
            industry_code=str(row.get("SecuritiesIndustryCode", row.get("產業別", ""))) or None,
            industry_name=str(row.get("SecuritiesIndustryName", row.get("產業別名稱", ""))) or None,
            listing_date=str(row.get("DateOfListing", row.get("上櫃日期", ""))) or None,
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
            return [
                record
                for row in response.json()
                if (record := self.map_row(row, as_of=received_at, received_at=received_at))
            ]
        finally:
            if close:
                await client.aclose()

    def map_daily_row(
        self, row: RawPriceRow, *, trade_date: date, received_at: datetime
    ) -> DailyPriceRecord | None:
        return make_daily_price(
            market=MarketCode.TPEX,
            code=row.get("SecuritiesCompanyCode", row.get("證券代號", "")),
            trade_date=row.get("Date", row.get("日期", trade_date.isoformat())),
            fallback_date=trade_date,
            open_=row.get("Open", row.get("開盤價", "")),
            high=row.get("High", row.get("最高價", "")),
            low=row.get("Low", row.get("最低價", "")),
            close=row.get("Close", row.get("收盤價", "")),
            volume=row.get("TradingShares", row.get("成交股數", "")),
            turnover=row.get("TransactionAmount", row.get("成交金額", "")),
            source_code="TPEX_DAILY",
            received_at=received_at,
        )

    def map_index_row(self, row, *, trade_date: date, received_at: datetime):
        return map_index(
            row,
            market=MarketCode.TPEX,
            code="OTC",
            name="櫃買指數",
            trade_date=trade_date,
            received_at=received_at,
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

    def map_margin_row(self, row, *, trade_date: date, received_at: datetime):
        code = str(row.get("SecuritiesCompanyCode", "")) or None
        return map_margin(
            row,
            market=MarketCode.TPEX,
            trade_date=trade_date,
            received_at=received_at,
            source="TPEX_MARGIN",
            keys={
                "margin_buy": "MarginPurchase",
                "margin_sell": "MarginSale",
                "margin_cash_repayment": "CashRedemption",
                "margin_balance": "MarginBalance",
                "short_sell": "ShortSale",
                "short_cover": "ShortCover",
                "short_stock_repayment": "StockRedemption",
                "short_balance": "ShortBalance",
                "short_margin_ratio": "ShortMarginRatio",
            },
            security_code=code,
        )

    def map_lending_row(self, row, *, trade_date: date, received_at: datetime):
        code = str(row.get("SecuritiesCompanyCode", "")) or None
        return map_lending(
            row,
            market=MarketCode.TPEX,
            trade_date=trade_date,
            received_at=received_at,
            source="TPEX_LENDING",
            keys={
                "lending_sell": "LendingSale",
                "lending_return": "LendingReturn",
                "lending_balance": "LendingBalance",
                "lending_balance_change": "LendingChange",
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
            response = await client.get(self.daily_endpoint)
            response.raise_for_status()
            received_at = datetime.now(UTC)
            mapped = [
                self.map_daily_row(row, trade_date=target, received_at=received_at)
                for row in response.json()
            ]
            return [
                item
                for item in mapped
                if item is not None
                and item.trade_date == target
                and (security is None or item.security == security)
            ]
        finally:
            if close:
                await client.aclose()
