from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.market_data import DataStatus
from app.domain.market_spot import (
    DealerSubtype,
    InstitutionalRecord,
    LendingRecord,
    MarginRecord,
    MarketIndexRecord,
    SourceMetadata,
)
from app.domain.pricing import SecurityKey
from app.domain.security import MarketCode


def decimal_value(value: Any) -> Decimal | None:
    if value in (None, "", "--", "---"):
        return None
    try:
        return Decimal(str(value).replace(",", "").replace("%", ""))
    except InvalidOperation:
        return None


def integer_value(value: Any, multiplier: int = 1) -> int | None:
    number = decimal_value(value)
    return int(number * multiplier) if number is not None else None


def metadata(source: str, trade_date: date, received_at: datetime, revision: str | None = None):
    return SourceMetadata(
        source,
        datetime.combine(trade_date, datetime.min.time(), received_at.tzinfo),
        received_at,
        DataStatus.FINAL,
        revision,
    )


def map_index(
    row: dict[str, Any],
    *,
    market: MarketCode,
    code: str,
    name: str,
    trade_date: date,
    received_at: datetime,
    source: str,
    keys: dict[str, str],
    turnover_multiplier: int = 1,
) -> MarketIndexRecord:
    def value(field: str) -> Decimal | None:
        return decimal_value(row.get(keys[field]))

    return MarketIndexRecord(
        code,
        name,
        market,
        trade_date,
        value("open"),
        value("high"),
        value("low"),
        value("close"),
        value("change"),
        value("change_percent"),
        (value("turnover") * turnover_multiplier if value("turnover") is not None else None),
        integer_value(row.get(keys["volume"])),
        metadata(source, trade_date, received_at),
    )


def map_institution(
    row: dict[str, Any],
    *,
    market: MarketCode,
    trade_date: date,
    received_at: datetime,
    source: str,
    institution,
    buy_key: str,
    sell_key: str,
    security_code: str | None = None,
    dealer_subtype: DealerSubtype | None = None,
    amount_multiplier: int = 1,
) -> InstitutionalRecord:
    buy = decimal_value(row.get(buy_key))
    sell = decimal_value(row.get(sell_key))
    if buy is not None:
        buy *= amount_multiplier
    if sell is not None:
        sell *= amount_multiplier
    return InstitutionalRecord(
        market,
        trade_date,
        institution,
        dealer_subtype,
        buy,
        sell,
        buy - sell if buy is not None and sell is not None else None,
        metadata(source, trade_date, received_at),
        SecurityKey(market, security_code) if security_code else None,
        security_code is None,
    )


def map_margin(
    row: dict[str, Any],
    *,
    market: MarketCode,
    trade_date: date,
    received_at: datetime,
    source: str,
    keys: dict[str, str],
    security_code: str | None = None,
    count_multiplier: int = 1,
) -> MarginRecord:
    def number(field: str) -> int | None:
        return integer_value(row.get(keys.get(field, "")), count_multiplier)

    return MarginRecord(
        market,
        trade_date,
        number("margin_buy"),
        number("margin_sell"),
        number("margin_cash_repayment"),
        number("margin_balance"),
        number("margin_balance_change"),
        number("short_sell"),
        number("short_cover"),
        number("short_stock_repayment"),
        number("short_balance"),
        number("short_balance_change"),
        decimal_value(row.get(keys.get("short_margin_ratio", ""))),
        metadata(source, trade_date, received_at),
        SecurityKey(market, security_code) if security_code else None,
    )


def map_lending(
    row: dict[str, Any],
    *,
    market: MarketCode,
    trade_date: date,
    received_at: datetime,
    source: str,
    keys: dict[str, str],
    security_code: str | None = None,
    count_multiplier: int = 1,
    data_status: DataStatus = DataStatus.FINAL,
    provider_policy=None,
) -> LendingRecord:
    def number(field: str) -> int | None:
        return integer_value(row.get(keys.get(field, "")), count_multiplier)

    return LendingRecord(
        market,
        trade_date,
        number("lending_short_sell"),
        number("lending_return"),
        number("lending_balance"),
        number("lending_balance_change"),
        SourceMetadata(
            source,
            datetime.combine(trade_date, datetime.min.time(), received_at.tzinfo),
            received_at,
            data_status,
            provider_policy=provider_policy,
        ),
        SecurityKey(market, security_code) if security_code else None,
    )
