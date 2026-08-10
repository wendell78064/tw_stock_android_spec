from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.domain.pricing import Candle

ALGORITHM_VERSION = "twml-technical-v1"
ZERO = Decimal(0)
HUNDRED = Decimal(100)


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, ZERO) / Decimal(len(values))


def sma(values: list[Decimal], period: int) -> list[Decimal | None]:
    return [
        None if index + 1 < period else _mean(values[index + 1 - period : index + 1])
        for index in range(len(values))
    ]


def ema(values: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = _mean(values[:period])
    result[period - 1] = current
    alpha = Decimal(2) / Decimal(period + 1)
    for index in range(period, len(values)):
        current = (values[index] - current) * alpha + current
        result[index] = current
    return result


def rsi(values: list[Decimal], period: int = 14) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(values)
    if len(values) <= period:
        return result
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    avg_gain = _mean([max(change, ZERO) for change in changes[:period]])
    avg_loss = _mean([max(-change, ZERO) for change in changes[:period]])
    for index in range(period, len(values)):
        if index > period:
            change = changes[index - 1]
            avg_gain = (avg_gain * Decimal(period - 1) + max(change, ZERO)) / Decimal(period)
            avg_loss = (avg_loss * Decimal(period - 1) + max(-change, ZERO)) / Decimal(period)
        result[index] = HUNDRED if avg_loss == 0 else HUNDRED - HUNDRED / (1 + avg_gain / avg_loss)
    return result


def macd(
    values: list[Decimal],
) -> tuple[list[Decimal | None], list[Decimal | None], list[Decimal | None]]:
    fast, slow = ema(values, 12), ema(values, 26)
    line = [None if a is None or b is None else a - b for a, b in zip(fast, slow, strict=True)]
    signal: list[Decimal | None] = [None] * len(values)
    available = [(i, value) for i, value in enumerate(line) if value is not None]
    if len(available) >= 9:
        seed_index = available[8][0]
        current = _mean([value for _, value in available[:9]])
        signal[seed_index] = current
        alpha = Decimal(2) / Decimal(10)
        for index, value in available[9:]:
            current = (value - current) * alpha + current
            signal[index] = current
    histogram = [
        None if a is None or b is None else a - b for a, b in zip(line, signal, strict=True)
    ]
    return line, signal, histogram


def stochastic(
    candles: list[Candle], period: int = 9
) -> tuple[list[Decimal | None], list[Decimal | None]]:
    k_values: list[Decimal | None] = [None] * len(candles)
    d_values: list[Decimal | None] = [None] * len(candles)
    k = d = Decimal(50)
    for index in range(period - 1, len(candles)):
        window = candles[index + 1 - period : index + 1]
        highest, lowest = max(item.high for item in window), min(item.low for item in window)
        if highest == lowest:
            continue
        rsv = (candles[index].close - lowest) / (highest - lowest) * HUNDRED
        k = (k * 2 + rsv) / 3
        d = (d * 2 + k) / 3
        k_values[index], d_values[index] = k, d
    return k_values, d_values


def atr(candles: list[Candle], period: int = 14) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(candles)
    if not candles:
        return result
    true_ranges = [candles[0].high - candles[0].low]
    for current, previous in zip(candles[1:], candles, strict=False):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    if len(true_ranges) < period:
        return result
    current = _mean(true_ranges[:period])
    result[period - 1] = current
    for index in range(period, len(true_ranges)):
        current = (current * Decimal(period - 1) + true_ranges[index]) / Decimal(period)
        result[index] = current
    return result


def obv(candles: list[Candle]) -> list[Decimal | None]:
    if not candles:
        return []
    result: list[Decimal | None] = [ZERO]
    current = ZERO
    for item, previous in zip(candles[1:], candles, strict=False):
        if item.volume_shares is None:
            result.append(None)
            continue
        volume = Decimal(item.volume_shares)
        current += (
            volume
            if item.close > previous.close
            else -volume
            if item.close < previous.close
            else ZERO
        )
        result.append(current)
    return result


def bollinger(
    values: list[Decimal], period: int = 20
) -> tuple[list[Decimal | None], list[Decimal | None], list[Decimal | None]]:
    middle = sma(values, period)
    upper: list[Decimal | None] = [None] * len(values)
    lower: list[Decimal | None] = [None] * len(values)
    with localcontext() as context:
        context.prec = 34
        for index in range(period - 1, len(values)):
            window = values[index + 1 - period : index + 1]
            mean = middle[index]
            assert mean is not None
            deviation = (_mean([(value - mean) ** 2 for value in window])).sqrt()
            upper[index], lower[index] = mean + deviation * 2, mean - deviation * 2
    return upper, middle, lower


def williams_r(candles: list[Candle], period: int = 14) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(candles)
    for index in range(period - 1, len(candles)):
        window = candles[index + 1 - period : index + 1]
        highest, lowest = max(item.high for item in window), min(item.low for item in window)
        if highest != lowest:
            result[index] = (highest - candles[index].close) / (highest - lowest) * Decimal(-100)
    return result


@dataclass(frozen=True)
class IndicatorSeries:
    values: list[dict[str, Decimal | None]]


class TechnicalIndicatorService:
    def calculate(self, candles: list[Candle]) -> IndicatorSeries:
        closes = [item.close for item in candles]
        values = [dict() for _ in candles]
        for period in (5, 10, 20, 60, 120, 240):
            for row, value in zip(values, sma(closes, period), strict=True):
                row[f"MA{period}"] = value
        for period in (12, 26):
            for row, value in zip(values, ema(closes, period), strict=True):
                row[f"EMA{period}"] = value
        for row, value in zip(values, rsi(closes), strict=True):
            row["RSI14"] = value
        macd_line, signal, histogram = macd(closes)
        k_values, d_values = stochastic(candles)
        upper, middle, lower = bollinger(closes)
        named = {
            "MACD": macd_line,
            "MACD_SIGNAL": signal,
            "MACD_HISTOGRAM": histogram,
            "KD_K": k_values,
            "KD_D": d_values,
            "ATR14": atr(candles),
            "OBV": obv(candles),
            "BBANDS_UPPER": upper,
            "BBANDS_MIDDLE": middle,
            "BBANDS_LOWER": lower,
            "WILLIAMS_R": williams_r(candles),
        }
        for name, series in named.items():
            for row, value in zip(values, series, strict=True):
                row[name] = value
        return IndicatorSeries(values)
