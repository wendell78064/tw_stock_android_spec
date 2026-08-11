from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.market_data import DataStatus

MA_PERIODS = {5, 10, 20, 60, 120, 240}
DEFAULT_NEAR_PERCENT = Decimal("1.0")
DEFAULT_COOLDOWN_MINUTES = 1440
DEFAULT_DAILY_LIMIT = 5


class AlertRuleType(StrEnum):
    PRICE_TARGET = "PRICE_TARGET"
    PRICE_STOP = "PRICE_STOP"
    PRICE_ADD = "PRICE_ADD"
    MA_NEAR = "MA_NEAR"
    MA_TOUCH = "MA_TOUCH"
    MA_CROSS_ABOVE = "MA_CROSS_ABOVE"
    MA_CROSS_BELOW = "MA_CROSS_BELOW"
    MA_CLOSE_ABOVE = "MA_CLOSE_ABOVE"
    MA_CLOSE_BELOW = "MA_CLOSE_BELOW"
    MA_CONSECUTIVE_ABOVE = "MA_CONSECUTIVE_ABOVE"
    MA_CONSECUTIVE_BELOW = "MA_CONSECUTIVE_BELOW"


class AlertScopeType(StrEnum):
    SECURITY = "SECURITY"
    PORTFOLIO = "PORTFOLIO"
    WATCHLIST = "WATCHLIST"


@dataclass(frozen=True)
class AlertRule:
    id: UUID
    name: str
    rule_type: AlertRuleType
    scope_type: AlertScopeType
    security_id: UUID | None
    portfolio_id: UUID | None
    watchlist_id: UUID | None
    ma_period: int | None
    threshold_price: Decimal | None
    threshold_percent: Decimal | None
    consecutive_days: int | None
    enabled: bool
    cooldown_minutes: int
    daily_limit: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class MarketPoint:
    security_id: UUID
    trade_date: date
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    moving_averages: dict[int, Decimal | None]
    data_status: DataStatus


@dataclass(frozen=True)
class AlertOccurrence:
    event_type: str
    trigger_price: Decimal
    reference_value: Decimal
    reference_type: str
    message: str
    data_status: DataStatus


@dataclass(frozen=True)
class AlertEvent:
    id: UUID
    alert_rule_id: UUID
    security_id: UUID
    security_code: str
    security_name: str
    triggered_at: datetime
    trade_date: date
    event_type: str
    trigger_price: Decimal
    reference_value: Decimal
    reference_type: str
    message: str
    data_status: DataStatus
    fingerprint: str
    notification_eligible: bool
    read_at: datetime | None
    created_at: datetime


def validate_rule(
    rule_type,
    scope_type,
    security_id,
    portfolio_id,
    watchlist_id,
    ma_period,
    threshold_price,
    threshold_percent,
    consecutive_days,
    cooldown_minutes,
    daily_limit,
) -> None:
    scope_values = {
        AlertScopeType.SECURITY: security_id,
        AlertScopeType.PORTFOLIO: portfolio_id,
        AlertScopeType.WATCHLIST: watchlist_id,
    }
    if (
        scope_values[scope_type] is None
        or sum(value is not None for value in scope_values.values()) != 1
    ):
        raise ValueError("exactly one scope target is required")
    is_price = rule_type.value.startswith("PRICE_")
    if (
        is_price != (threshold_price is not None)
        or threshold_price is not None
        and threshold_price <= 0
    ):
        raise ValueError("price rules require a positive threshold_price")
    is_ma = rule_type.value.startswith("MA_")
    if is_ma and ma_period not in MA_PERIODS or not is_ma and ma_period is not None:
        raise ValueError("MA rules require a supported ma_period")
    if rule_type is AlertRuleType.MA_NEAR:
        if threshold_percent is None or not Decimal("0") < threshold_percent <= Decimal("20"):
            raise ValueError("MA_NEAR threshold_percent must be within (0,20]")
    elif threshold_percent is not None:
        raise ValueError("threshold_percent is only valid for MA_NEAR")
    consecutive = rule_type in {
        AlertRuleType.MA_CONSECUTIVE_ABOVE,
        AlertRuleType.MA_CONSECUTIVE_BELOW,
    }
    if consecutive and (consecutive_days is None or not 2 <= consecutive_days <= 60):
        raise ValueError("consecutive_days must be within [2,60]")
    if not consecutive and consecutive_days is not None:
        raise ValueError("consecutive_days is only valid for consecutive rules")
    if cooldown_minutes < 0 or daily_limit < 1:
        raise ValueError("cooldown and daily_limit are invalid")
