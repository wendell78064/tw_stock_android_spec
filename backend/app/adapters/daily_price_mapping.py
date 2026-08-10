from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from app.domain.market_data import DataStatus
from app.domain.pricing import DailyPriceRecord, SecurityKey
from app.domain.security import MarketCode

RawPriceRow = Mapping[str, object]
MISSING = {"", "--", "---", "-", "除權", "除息"}


def decimal_or_none(value: object) -> Decimal | None:
    text = str(value).strip().replace(",", "")
    if text in MISSING:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def integer_or_none(value: object) -> int | None:
    number = decimal_or_none(value)
    return None if number is None else int(number)


def parse_trade_date(value: object, fallback: date | None = None) -> date | None:
    text = str(value).strip().replace("/", "").replace("-", "")
    if len(text) == 8 and text.isdigit():
        return date(int(text[:4]), int(text[4:6]), int(text[6:]))
    if len(text) == 7 and text.isdigit():
        return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:]))
    return fallback


def make_daily_price(
    *,
    market: MarketCode,
    code: object,
    trade_date: object,
    fallback_date: date | None,
    open_: object,
    high: object,
    low: object,
    close: object,
    volume: object,
    turnover: object,
    source_code: str,
    received_at: datetime,
    adjusted_close: object | None = None,
    revision: str | None = None,
) -> DailyPriceRecord | None:
    parsed_date = parse_trade_date(trade_date, fallback_date)
    security_code = str(code).strip()
    if parsed_date is None or not security_code:
        return None
    raw = tuple(decimal_or_none(value) for value in (open_, high, low, close))
    has_trade = all(value is not None for value in raw)
    adjusted = decimal_or_none(adjusted_close) if adjusted_close is not None else None
    as_of = datetime.combine(parsed_date, datetime.min.time(), tzinfo=UTC)
    return DailyPriceRecord(
        security=SecurityKey(market, security_code),
        trade_date=parsed_date,
        open=raw[0],
        high=raw[1],
        low=raw[2],
        close=raw[3],
        adjusted_open=None,
        adjusted_high=None,
        adjusted_low=None,
        adjusted_close=adjusted,
        volume_shares=integer_or_none(volume),
        turnover_amount=decimal_or_none(turnover),
        source_code=source_code,
        as_of=as_of,
        received_at=received_at.astimezone(UTC),
        data_status=DataStatus.FINAL if has_trade else DataStatus.UNAVAILABLE,
        source_revision=revision,
        missing_reason=None if has_trade else "NO_TRADE_OR_MISSING_OHLC",
    )
