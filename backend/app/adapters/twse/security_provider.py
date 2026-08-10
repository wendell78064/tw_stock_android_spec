from datetime import UTC, datetime

import httpx

from app.adapters.security_mapping import RawRow, make_record
from app.domain.security import MarketCode, SecurityRecord


class TwseSecurityProvider:
    source_code = "TWSE"
    endpoint = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"

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
