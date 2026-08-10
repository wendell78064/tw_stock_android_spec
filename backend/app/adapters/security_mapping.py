import re
from collections.abc import Mapping
from datetime import UTC, date, datetime

from app.domain.market_data import DataStatus
from app.domain.security import Industry, MarketCode, SecurityRecord, SecurityStatus, SecurityType

COMMON_STOCK_CODE = re.compile(r"^[1-8][0-9]{3}$")


def parse_roc_date(value: str | None) -> date | None:
    if not value or not value.strip():
        return None
    normalized = value.strip().replace("/", "")
    if len(normalized) != 7 or not normalized.isdigit():
        return None
    return date(int(normalized[:3]) + 1911, int(normalized[3:5]), int(normalized[5:7]))


def is_common_stock_code(code: str) -> bool:
    return bool(COMMON_STOCK_CODE.fullmatch(code.strip()))


def make_record(
    *,
    market: MarketCode,
    code: str,
    name: str,
    industry_code: str | None,
    industry_name: str | None,
    listing_date: str | None,
    source_code: str,
    as_of: datetime,
    received_at: datetime,
) -> SecurityRecord | None:
    code = code.strip()
    if not is_common_stock_code(code) or not name.strip():
        return None
    industry = None
    if industry_code and industry_name:
        industry = Industry(industry_code.strip(), industry_name.strip(), source_code)
    return SecurityRecord(
        market=market,
        code=code,
        name=name.strip(),
        security_type=SecurityType.COMMON_STOCK,
        status=SecurityStatus.ACTIVE,
        listing_date=parse_roc_date(listing_date),
        industry=industry,
        source_code=source_code,
        as_of=as_of.astimezone(UTC),
        received_at=received_at.astimezone(UTC),
        data_status=DataStatus.FINAL,
    )


RawRow = Mapping[str, object]
