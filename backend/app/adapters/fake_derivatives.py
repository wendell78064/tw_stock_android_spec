from calendar import monthcalendar
from datetime import UTC, date, datetime
from decimal import Decimal

from app.domain.derivatives import (
    ContractStatus,
    FuturesContract,
    FuturesDailyPrice,
    FuturesProduct,
    InstitutionFuturesPosition,
    OptionPutCallRatio,
    OptionStrikeOpenInterest,
    OptionType,
    PositionSide,
    SessionType,
    TraderConcentration,
    VolatilityIndex,
)
from app.domain.market_data import DataStatus
from app.domain.market_spot import InstitutionType, SourceMetadata

PRODUCTS = (
    ("TX", "臺股期貨", "200"),
    ("MTX", "小型臺指", "50"),
    ("TMF", "微型臺指", "10"),
    ("TE", "電子期貨", "4000"),
    ("TF", "金融期貨", "1000"),
)


def third_wednesday(year: int, month: int) -> date:
    weeks = monthcalendar(year, month)
    days = [week[2] for week in weeks if week[2]]
    return date(year, month, days[2])


def add_month(year: int, month: int, offset: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + offset
    return index // 12, index % 12 + 1


class FakeDerivativesDataProvider:
    source_code = "FAKE_TAIFEX"

    @staticmethod
    def _meta(target: date) -> SourceMetadata:
        as_of = datetime(target.year, target.month, target.day, tzinfo=UTC)
        return SourceMetadata(
            "FAKE_TAIFEX", as_of, as_of.replace(hour=8), DataStatus.FINAL, "fixture-v1"
        )

    async def get_futures_products(self) -> list[FuturesProduct]:
        return [
            FuturesProduct(code, name, Decimal(multiplier), "TWD", SessionType.COMBINED)
            for code, name, multiplier in PRODUCTS
        ]

    async def get_futures_contracts(self, trade_date: date) -> list[FuturesContract]:
        result = []
        for product, _, _ in PRODUCTS:
            for offset in range(2):
                year, month = add_month(trade_date.year, trade_date.month, offset)
                expiry = third_wednesday(year, month)
                result.append(
                    FuturesContract(
                        product,
                        f"{product}{year}{month:02d}",
                        f"{year}{month:02d}",
                        expiry,
                        expiry,
                        ContractStatus.ACTIVE if expiry >= trade_date else ContractStatus.EXPIRED,
                        expiry >= trade_date,
                    )
                )
        return result

    async def get_futures_daily(self, trade_date: date) -> list[FuturesDailyPrice]:
        ordinal = (trade_date - date(2026, 1, 1)).days
        records = []
        for product_index, (product, _, _) in enumerate(PRODUCTS):
            for offset in range(2):
                year, month = add_month(trade_date.year, trade_date.month, offset)
                contract = f"{product}{year}{month:02d}"
                base = Decimal(22000 + ordinal * 3 + product_index * 100 + offset * 30)
                oi = 80000 - offset * 25000 + product_index * 1000 + ordinal
                records.append(
                    FuturesDailyPrice(
                        product,
                        contract,
                        f"{year}{month:02d}",
                        trade_date,
                        SessionType.COMBINED,
                        base - 20,
                        base + 80,
                        base - 70,
                        base + 30,
                        base + 25,
                        Decimal("30"),
                        Decimal("0.14"),
                        120000 - offset * 40000 + product_index * 1000,
                        oi,
                        self._meta(trade_date),
                    )
                )
        return records

    async def get_futures_institutional_positions(
        self, trade_date: date
    ) -> list[InstitutionFuturesPosition]:
        ordinal = (trade_date - date(2026, 1, 1)).days
        rows = []
        for product, _, _ in PRODUCTS:
            for index, institution in enumerate(
                (InstitutionType.FOREIGN, InstitutionType.INVESTMENT_TRUST, InstitutionType.DEALER)
            ):
                long_oi = 32000 + ordinal * (index + 1)
                short_oi = 95000 - ordinal * (index + 1)
                long_volume, short_volume = long_oi // 2, short_oi // 2
                rows.append(
                    InstitutionFuturesPosition(
                        product,
                        trade_date,
                        institution,
                        long_volume,
                        short_volume,
                        long_volume - short_volume,
                        Decimal(long_volume * 1000),
                        Decimal(short_volume * 1000),
                        Decimal((long_volume - short_volume) * 1000),
                        long_oi,
                        short_oi,
                        long_oi - short_oi,
                        Decimal(long_oi * 1000),
                        Decimal(short_oi * 1000),
                        Decimal((long_oi - short_oi) * 1000),
                        self._meta(trade_date),
                    )
                )
        return rows

    async def get_trader_concentration(self, trade_date: date) -> list[TraderConcentration]:
        rows = []
        for product, _, _ in PRODUCTS:
            for top_n in (5, 10):
                for side in PositionSide:
                    oi = (30000 if side is PositionSide.LONG else 34000) + top_n * 100
                    market_oi = 100000
                    rows.append(
                        TraderConcentration(
                            product,
                            trade_date,
                            "ALL_MONTHS",
                            side,
                            top_n,
                            oi,
                            market_oi,
                            Decimal(oi) / Decimal(market_oi) * 100,
                            None,
                            self._meta(trade_date),
                        )
                    )
        return rows

    async def get_put_call_ratio(self, trade_date: date) -> list[OptionPutCallRatio]:
        ordinal = (trade_date - date(2026, 1, 1)).days
        put_volume, call_volume = 330000 + ordinal, 320000 + ordinal
        put_oi, call_oi = 60000 + ordinal, 56000 + ordinal
        return [
            OptionPutCallRatio(
                "TXO",
                trade_date,
                put_volume,
                call_volume,
                Decimal(put_volume) / Decimal(call_volume) * 100,
                put_oi,
                call_oi,
                Decimal(put_oi) / Decimal(call_oi) * 100,
                self._meta(trade_date),
            )
        ]

    async def get_option_open_interest_by_strike(
        self, trade_date: date
    ) -> list[OptionStrikeOpenInterest]:
        expiry = f"{trade_date.year}{trade_date.month:02d}"
        rows = []
        for strike in range(21500, 22600, 100):
            for option_type in OptionType:
                distance = abs(strike - 22000)
                oi = 12000 - distance * 10 + (500 if option_type is OptionType.PUT else 0)
                rows.append(
                    OptionStrikeOpenInterest(
                        "TXO",
                        expiry,
                        trade_date,
                        option_type,
                        Decimal(strike),
                        max(oi, 100),
                        1000,
                        Decimal("10.5"),
                        self._meta(trade_date),
                    )
                )
        return rows

    async def get_volatility_index(self, trade_date: date) -> list[VolatilityIndex]:
        value = Decimal("18") + Decimal((trade_date - date(2026, 1, 1)).days % 20) / 10
        return [
            VolatilityIndex(
                "TAIWAN_VIX",
                trade_date,
                value - Decimal("0.3"),
                value + Decimal("0.5"),
                value - Decimal("0.6"),
                value,
                self._meta(trade_date),
            )
        ]
