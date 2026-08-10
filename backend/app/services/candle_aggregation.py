from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.domain.pricing import Candle, CandleInterval, DailyPriceRecord, PriceBasis


def price_candle(record: DailyPriceRecord, basis: PriceBasis) -> Candle | None:
    values = (
        (record.open, record.high, record.low, record.close)
        if basis is PriceBasis.RAW
        else (
            record.adjusted_open,
            record.adjusted_high,
            record.adjusted_low,
            record.adjusted_close,
        )
    )
    if any(value is None for value in values):
        return None
    open_, high, low, close = values
    assert isinstance(open_, Decimal)
    assert isinstance(high, Decimal)
    assert isinstance(low, Decimal)
    assert isinstance(close, Decimal)
    return Candle(
        record.trade_date,
        open_,
        high,
        low,
        close,
        record.volume_shares,
        record.turnover_amount,
    )


class CandleAggregationService:
    def aggregate(
        self, records: list[DailyPriceRecord], interval: CandleInterval, basis: PriceBasis
    ) -> list[Candle]:
        daily = [
            item
            for record in sorted(records, key=lambda row: row.trade_date)
            if (item := price_candle(record, basis)) is not None
        ]
        if interval is CandleInterval.DAY:
            return daily
        groups: dict[tuple[int, int], list[Candle]] = defaultdict(list)
        for candle in daily:
            if interval is CandleInterval.WEEK:
                iso_year, iso_week, _ = candle.trade_date.isocalendar()
                key = (iso_year, iso_week)
            else:
                key = (candle.trade_date.year, candle.trade_date.month)
            groups[key].append(candle)
        return [self._merge(group) for group in groups.values()]

    @staticmethod
    def _merge(candles: list[Candle]) -> Candle:
        first, last = candles[0], candles[-1]
        volume = (
            None
            if any(item.volume_shares is None for item in candles)
            else sum(item.volume_shares or 0 for item in candles)
        )
        turnover = (
            None
            if any(item.turnover_amount is None for item in candles)
            else sum((item.turnover_amount or Decimal(0) for item in candles), Decimal(0))
        )
        return Candle(
            trade_date=last.trade_date,
            open=first.open,
            high=max(item.high for item in candles),
            low=min(item.low for item in candles),
            close=last.close,
            volume_shares=volume,
            turnover_amount=turnover,
        )


def range_start(end: date, range_name: str) -> date:
    days = {"1D": 10, "5D": 20, "10D": 30, "30D": 60, "1Y": 370, "5Y": 1835}
    from datetime import timedelta

    return end - timedelta(days=days[range_name])
