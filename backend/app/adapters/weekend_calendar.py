from datetime import date, timedelta


class WeekendOnlyCalendar:
    """Development fallback only; production must use the Taiwan exchange calendar."""

    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5

    def previous_trading_day(self, value: date) -> date:
        candidate = value - timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate -= timedelta(days=1)
        return candidate
