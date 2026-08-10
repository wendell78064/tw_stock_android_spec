from datetime import date, timedelta
from decimal import Decimal

from app.domain.pricing import Candle
from app.services.technical_indicators import TechnicalIndicatorService


def fixture(count: int = 260) -> list[Candle]:
    day = date(2025, 1, 1)
    candles = []
    for index in range(count):
        value = Decimal(100 + index)
        candles.append(
            Candle(
                day + timedelta(days=index * 2),
                value,
                value + 2,
                value - 1,
                value + 1,
                1000 + index,
                Decimal(100000 + index),
            )
        )
    return candles


def test_all_indicators_are_deterministic_and_long_ma_requires_history() -> None:
    values = TechnicalIndicatorService().calculate(fixture()).values
    last = values[-1]
    assert last["MA5"] == Decimal("358")
    assert last["MA10"] == Decimal("355.5")
    assert last["MA20"] == Decimal("350.5")
    assert last["MA60"] == Decimal("330.5")
    assert last["MA120"] == Decimal("300.5")
    assert last["MA240"] == Decimal("240.5")
    for name in (
        "EMA12",
        "EMA26",
        "RSI14",
        "MACD",
        "MACD_SIGNAL",
        "MACD_HISTOGRAM",
        "KD_K",
        "KD_D",
        "ATR14",
        "OBV",
        "BBANDS_UPPER",
        "BBANDS_MIDDLE",
        "BBANDS_LOWER",
        "WILLIAMS_R",
    ):
        assert last[name] is not None
    short = TechnicalIndicatorService().calculate(fixture(10)).values[-1]
    assert short["MA20"] is None and short["RSI14"] is None and short["ATR14"] is None


def test_sequence_uses_rows_not_natural_day_interpolation() -> None:
    result = TechnicalIndicatorService().calculate(fixture(5)).values
    assert result[-1]["MA5"] == Decimal("103")
