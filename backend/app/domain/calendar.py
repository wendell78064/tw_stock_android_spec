from datetime import date
from typing import Protocol


class TradingCalendar(Protocol):
    def is_trading_day(self, value: date) -> bool: ...

    def previous_trading_day(self, value: date) -> date: ...
