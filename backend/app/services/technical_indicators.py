from dataclasses import dataclass
from decimal import Decimal, localcontext

from app.domain.pricing import Candle

ALGORITHM_VERSION = "twml-technical-v1"
REQUEST_ALGORITHM_VERSION = "twml-technical-v1-request"
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
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[list[Decimal | None], list[Decimal | None], list[Decimal | None]]:
    fast, slow = ema(values, fast_period), ema(values, slow_period)
    line = [None if a is None or b is None else a - b for a, b in zip(fast, slow, strict=True)]
    signal: list[Decimal | None] = [None] * len(values)
    available = [(i, value) for i, value in enumerate(line) if value is not None]
    if len(available) >= signal_period:
        seed_index = available[signal_period - 1][0]
        current = _mean([value for _, value in available[:signal_period]])
        signal[seed_index] = current
        alpha = Decimal(2) / Decimal(signal_period + 1)
        for index, value in available[signal_period:]:
            current = (value - current) * alpha + current
            signal[index] = current
    histogram = [
        None if a is None or b is None else a - b for a, b in zip(line, signal, strict=True)
    ]
    return line, signal, histogram


def stochastic(
    candles: list[Candle],
    period: int = 9,
    k_smoothing: int = 3,
    d_smoothing: int = 3,
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
        k = (k * Decimal(k_smoothing - 1) + rsv) / Decimal(k_smoothing)
        d = (d * Decimal(d_smoothing - 1) + k) / Decimal(d_smoothing)
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
    values: list[Decimal],
    period: int = 20,
    multiplier: Decimal = Decimal(2),
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
            upper[index], lower[index] = (
                mean + deviation * multiplier,
                mean - deviation * multiplier,
            )
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


@dataclass(frozen=True)
class TechnicalParameters:
    ma_periods: tuple[int, ...] = (5, 10, 20, 60, 120, 240)
    ema_periods: tuple[int, ...] = (12, 26)
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    kd_period: int = 9
    kd_k_smoothing: int = 3
    kd_d_smoothing: int = 3
    bollinger_period: int = 20
    bollinger_stddev: Decimal = Decimal(2)
    atr_period: int = 14
    williams_period: int = 14

    def validate(self) -> None:
        periods = (
            *self.ma_periods,
            *self.ema_periods,
            self.rsi_period,
            self.macd_fast,
            self.macd_slow,
            self.macd_signal,
            self.kd_period,
            self.kd_k_smoothing,
            self.kd_d_smoothing,
            self.bollinger_period,
            self.atr_period,
            self.williams_period,
        )
        if any(value <= 0 for value in periods):
            raise ValueError("technical indicator periods must be greater than zero")
        if len(set(self.ma_periods)) != len(self.ma_periods):
            raise ValueError("MA periods must not contain duplicates")
        if self.macd_slow <= self.macd_fast:
            raise ValueError("MACD slow must be greater than fast")
        if self.bollinger_stddev <= 0:
            raise ValueError("Bollinger standard deviation multiplier must be greater than zero")

    def response_parameters(self) -> dict[str, dict[str, int | str]]:
        result = {f"MA{p}": {"period": p} for p in self.ma_periods}
        result.update({f"EMA{p}": {"period": p} for p in self.ema_periods})
        result[f"RSI{self.rsi_period}"] = {"period": self.rsi_period}
        result.update(
            {
                name: {"fast": self.macd_fast, "slow": self.macd_slow, "signal": self.macd_signal}
                for name in ("MACD", "MACD_SIGNAL", "MACD_HISTOGRAM")
            }
        )
        result.update(
            {
                name: {
                    "period": self.kd_period,
                    "k_smoothing": self.kd_k_smoothing,
                    "d_smoothing": self.kd_d_smoothing,
                }
                for name in ("KD_K", "KD_D")
            }
        )
        result.update(
            {
                name: {"period": self.bollinger_period, "stddev": str(self.bollinger_stddev)}
                for name in ("BBANDS_UPPER", "BBANDS_MIDDLE", "BBANDS_LOWER")
            }
        )
        result[f"ATR{self.atr_period}"] = {"period": self.atr_period}
        result["WILLIAMS_R"] = {"period": self.williams_period}
        result["OBV"] = {}
        return result


class TechnicalIndicatorService:
    def calculate(
        self, candles: list[Candle], parameters: TechnicalParameters | None = None
    ) -> IndicatorSeries:
        parameters = parameters or TechnicalParameters()
        parameters.validate()
        closes = [item.close for item in candles]
        values = [dict() for _ in candles]
        for period in parameters.ma_periods:
            for row, value in zip(values, sma(closes, period), strict=True):
                row[f"MA{period}"] = value
        for period in parameters.ema_periods:
            for row, value in zip(values, ema(closes, period), strict=True):
                row[f"EMA{period}"] = value
        for row, value in zip(values, rsi(closes, parameters.rsi_period), strict=True):
            row[f"RSI{parameters.rsi_period}"] = value
        macd_line, signal, histogram = macd(
            closes, parameters.macd_fast, parameters.macd_slow, parameters.macd_signal
        )
        k_values, d_values = stochastic(
            candles, parameters.kd_period, parameters.kd_k_smoothing, parameters.kd_d_smoothing
        )
        upper, middle, lower = bollinger(
            closes, parameters.bollinger_period, parameters.bollinger_stddev
        )
        named = {
            "MACD": macd_line,
            "MACD_SIGNAL": signal,
            "MACD_HISTOGRAM": histogram,
            "KD_K": k_values,
            "KD_D": d_values,
            f"ATR{parameters.atr_period}": atr(candles, parameters.atr_period),
            "OBV": obv(candles),
            "BBANDS_UPPER": upper,
            "BBANDS_MIDDLE": middle,
            "BBANDS_LOWER": lower,
            "WILLIAMS_R": williams_r(candles, parameters.williams_period),
        }
        for name, series in named.items():
            for row, value in zip(values, series, strict=True):
                row[name] = value
        return IndicatorSeries(values)
