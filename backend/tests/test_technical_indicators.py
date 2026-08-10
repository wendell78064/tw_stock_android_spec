from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.domain.pricing import Candle
from app.services.technical_indicators import TechnicalIndicatorService, TechnicalParameters


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


def test_custom_parameters_and_validation() -> None:
    parameters = TechnicalParameters(
        ma_periods=(3,),
        ema_periods=(4,),
        rsi_period=12,
        macd_fast=10,
        macd_slow=24,
        macd_signal=8,
        kd_period=7,
        kd_k_smoothing=2,
        kd_d_smoothing=4,
        bollinger_period=15,
        bollinger_stddev=Decimal("2.5"),
        atr_period=10,
        williams_period=11,
    )
    last = TechnicalIndicatorService().calculate(fixture(), parameters).values[-1]
    assert last["MA3"] is not None and last["EMA4"] is not None and last["RSI12"] is not None
    assert last["ATR10"] is not None and last["WILLIAMS_R"] is not None
    with pytest.raises(ValueError, match="slow"):
        TechnicalParameters(macd_fast=26, macd_slow=12).validate()
    with pytest.raises(ValueError, match="Bollinger"):
        TechnicalParameters(bollinger_stddev=Decimal(0)).validate()
    with pytest.raises(ValueError, match="duplicates"):
        TechnicalParameters(ma_periods=(5, 5)).validate()
