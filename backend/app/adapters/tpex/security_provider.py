from datetime import UTC, datetime

import httpx

from app.adapters.security_mapping import RawRow, make_record
from app.domain.security import MarketCode, SecurityRecord


class TpexSecurityProvider:
    source_code = "TPEX"
    endpoint = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

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
