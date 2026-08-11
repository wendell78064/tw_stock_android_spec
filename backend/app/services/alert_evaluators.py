from decimal import Decimal

from app.domain.alert import AlertOccurrence, AlertRule, AlertRuleType, MarketPoint
from app.domain.market_data import DataStatus


def evaluate(rule: AlertRule, history: list[MarketPoint], code: str) -> AlertOccurrence | None:
    if not history:
        return None
    current = history[-1]
    if current.close is None or current.data_status is DataStatus.UNAVAILABLE:
        return None
    previous = history[-2] if len(history) > 1 else None
    kind = rule.rule_type
    reference: Decimal | None = rule.threshold_price
    hit = False
    label = ""
    if kind in {AlertRuleType.PRICE_TARGET, AlertRuleType.PRICE_STOP, AlertRuleType.PRICE_ADD}:
        if (
            previous is None
            or previous.close is None
            or previous.data_status is DataStatus.UNAVAILABLE
            or reference is None
        ):
            return None
        if kind is AlertRuleType.PRICE_TARGET:
            hit, label = previous.close < reference <= current.close, "收盤突破設定目標價"
        elif kind is AlertRuleType.PRICE_STOP:
            hit, label = previous.close > reference >= current.close, "收盤跌破設定停損價"
        else:
            hit, label = previous.close > reference >= current.close, "收盤跌破設定加碼價"
        reference_type = kind.value.removeprefix("PRICE_") + "_PRICE"
    else:
        assert rule.ma_period is not None
        reference = current.moving_averages.get(rule.ma_period)
        if reference is None:
            return None
        reference_type = f"MA{rule.ma_period}"
        if kind is AlertRuleType.MA_NEAR:
            hit = abs(current.close - reference) / reference * 100 <= rule.threshold_percent
            label = "收盤接近"
        elif kind is AlertRuleType.MA_TOUCH:
            hit = (
                current.low is not None
                and current.high is not None
                and current.low <= reference <= current.high
            )
            label = "今日價格區間觸及"
        elif kind in {AlertRuleType.MA_CROSS_ABOVE, AlertRuleType.MA_CROSS_BELOW}:
            if (
                previous is None
                or previous.close is None
                or previous.data_status is DataStatus.UNAVAILABLE
            ):
                return None
            previous_ma = previous.moving_averages.get(rule.ma_period)
            if previous_ma is None:
                return None
            if kind is AlertRuleType.MA_CROSS_ABOVE:
                hit, label = (
                    previous.close <= previous_ma and current.close > reference,
                    "收盤由均線下方突破至上方",
                )
            else:
                hit, label = (
                    previous.close >= previous_ma and current.close < reference,
                    "收盤由均線上方跌破至下方",
                )
        elif kind in {AlertRuleType.MA_CLOSE_ABOVE, AlertRuleType.MA_CLOSE_BELOW}:
            hit = (
                current.close > reference
                if kind is AlertRuleType.MA_CLOSE_ABOVE
                else current.close < reference
            )
            label = "收盤高於" if kind is AlertRuleType.MA_CLOSE_ABOVE else "收盤低於"
        else:
            count = rule.consecutive_days or 0
            if len(history) < count:
                return None
            points = history[-count:]
            comparisons = [
                (point.close, point.moving_averages.get(rule.ma_period)) for point in points
            ]
            if any(point.data_status is DataStatus.UNAVAILABLE for point in points) or any(
                close is None or ma is None for close, ma in comparisons
            ):
                return None
            above = kind is AlertRuleType.MA_CONSECUTIVE_ABOVE
            hit = all(close > ma if above else close < ma for close, ma in comparisons)
            label = f"已連續 {count} 個交易日收盤{'高於' if above else '低於'}"
    if not hit or reference is None:
        return None
    return AlertOccurrence(
        kind.value,
        current.close,
        reference,
        reference_type,
        f"{code} {label} {reference_type}",
        current.data_status,
    )
