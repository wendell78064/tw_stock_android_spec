from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domain.market_data import DataStatus
from app.domain.security import MarketCode


class ScreenerOperator(StrEnum):
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    EQ = "EQ"
    NE = "NE"
    BETWEEN = "BETWEEN"
    IN = "IN"
    NOT_IN = "NOT_IN"
    IS_AVAILABLE = "IS_AVAILABLE"
    IS_UNAVAILABLE = "IS_UNAVAILABLE"


class FilterCategory(StrEnum):
    PRICE_RETURN = "PRICE_RETURN"
    TECHNICAL = "TECHNICAL"
    INSTITUTIONAL = "INSTITUTIONAL"
    CREDIT = "CREDIT"
    TAXONOMY = "TAXONOMY"
    INDUSTRY_STRENGTH = "INDUSTRY_STRENGTH"


class FieldType(StrEnum):
    NUMERIC = "NUMERIC"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"


@dataclass
class ScreenerFieldMeta:
    field_id: str
    label: str
    category: FilterCategory
    value_type: FieldType
    allowed_operators: list[ScreenerOperator]
    unit: str | None = None
    supported_windows: list[int] | None = None


SCREENER_FIELDS_REGISTRY: dict[str, ScreenerFieldMeta] = {
    "close": ScreenerFieldMeta(
        field_id="close",
        label="收盤價",
        category=FilterCategory.PRICE_RETURN,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
            ScreenerOperator.BETWEEN,
            ScreenerOperator.IS_AVAILABLE,
        ],
        unit="TWD",
    ),
    "return_1d": ScreenerFieldMeta(
        field_id="return_1d",
        label="1日漲跌幅",
        category=FilterCategory.PRICE_RETURN,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
            ScreenerOperator.BETWEEN,
        ],
        unit="%",
    ),
    "return_5d": ScreenerFieldMeta(
        field_id="return_5d",
        label="5日漲跌幅",
        category=FilterCategory.PRICE_RETURN,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
            ScreenerOperator.BETWEEN,
        ],
        unit="%",
    ),
    "rsi14": ScreenerFieldMeta(
        field_id="rsi14",
        label="RSI(14)",
        category=FilterCategory.TECHNICAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
            ScreenerOperator.BETWEEN,
        ],
    ),
    "close_vs_ma20": ScreenerFieldMeta(
        field_id="close_vs_ma20",
        label="股價相對於 MA20",
        category=FilterCategory.TECHNICAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="%",
    ),
    "close_vs_ma60": ScreenerFieldMeta(
        field_id="close_vs_ma60",
        label="股價相對於 MA60",
        category=FilterCategory.TECHNICAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="%",
    ),
    "close_vs_ma240": ScreenerFieldMeta(
        field_id="close_vs_ma240",
        label="股價相對於 MA240",
        category=FilterCategory.TECHNICAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="%",
    ),
    "foreign_5d_net": ScreenerFieldMeta(
        field_id="foreign_5d_net",
        label="外資5日累計買賣超",
        category=FilterCategory.INSTITUTIONAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="股",
    ),
    "trust_5d_net": ScreenerFieldMeta(
        field_id="trust_5d_net",
        label="投信5日累計買賣超",
        category=FilterCategory.INSTITUTIONAL,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="股",
    ),
    "margin_balance_change": ScreenerFieldMeta(
        field_id="margin_balance_change",
        label="融資餘額變動",
        category=FilterCategory.CREDIT,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
        ],
        unit="股",
    ),
    "industry_name": ScreenerFieldMeta(
        field_id="industry_name",
        label="官方產業名稱",
        category=FilterCategory.TAXONOMY,
        value_type=FieldType.TEXT,
        allowed_operators=[
            ScreenerOperator.EQ,
            ScreenerOperator.NE,
            ScreenerOperator.IN,
            ScreenerOperator.NOT_IN,
        ],
    ),
    "theme_name": ScreenerFieldMeta(
        field_id="theme_name",
        label="自訂題材名稱",
        category=FilterCategory.TAXONOMY,
        value_type=FieldType.TEXT,
        allowed_operators=[
            ScreenerOperator.EQ,
            ScreenerOperator.NE,
            ScreenerOperator.IN,
            ScreenerOperator.NOT_IN,
        ],
    ),
    "industry_strength_score": ScreenerFieldMeta(
        field_id="industry_strength_score",
        label="產業強度分數",
        category=FilterCategory.INDUSTRY_STRENGTH,
        value_type=FieldType.NUMERIC,
        allowed_operators=[
            ScreenerOperator.GT,
            ScreenerOperator.GTE,
            ScreenerOperator.LT,
            ScreenerOperator.LTE,
            ScreenerOperator.BETWEEN,
        ],
    ),
}


@dataclass
class ScreenerExpression:
    type: str  # "CONDITION", "AND", "OR"
    field: str | None = None
    operator: ScreenerOperator | None = None
    value: Any = None
    value2: Any = None
    children: list["ScreenerExpression"] = dc_field(default_factory=list)


@dataclass
class SavedScreener:
    id: UUID
    name: str
    description: str | None
    expression: ScreenerExpression
    sort_field: str
    sort_direction: str
    created_at: datetime
    updated_at: datetime


@dataclass
class ScreenerResultSecurity:
    security_id: UUID
    code: str
    name: str
    market: MarketCode
    industry_name: str | None
    themes: list[str]
    close: str | None
    return_pct: str | None
    matched_conditions: list[str]
    extra_metrics: dict[str, Any]
    data_status: DataStatus
