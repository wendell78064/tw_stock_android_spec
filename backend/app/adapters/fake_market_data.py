from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.market_data import DataStatus, MarketSnapshot
from app.domain.market_spot import (
    DealerSubtype,
    InstitutionalRecord,
    InstitutionType,
    LendingRecord,
    MarginRecord,
    MarketBreadthRecord,
    MarketIndexRecord,
    SourceMetadata,
)
from app.domain.pricing import DailyPriceRecord, SecurityKey
from app.domain.security import Industry, MarketCode, SecurityRecord, SecurityStatus, SecurityType


class FakeMarketDataProvider:
    """Deterministic no-market-value provider for tests and Phase 0 wiring."""

    async def get_snapshot(self, symbol: str) -> MarketSnapshot:
        now = datetime.now(UTC)
        return MarketSnapshot(
            symbol=symbol,
            price=None,
            as_of=now,
            received_at=now,
            data_status=DataStatus.UNAVAILABLE,
            missing_reason="Phase 0 fake provider contains no market data",
        )

    async def list_securities(self) -> list[SecurityRecord]:
        now = datetime(2026, 8, 6, 0, 0, tzinfo=UTC)
        return [
            SecurityRecord(
                market=MarketCode.TWSE,
                code="1234",
                name="測試科技",
                security_type=SecurityType.COMMON_STOCK,
                status=SecurityStatus.ACTIVE,
                listing_date=None,
                industry=Industry("TEST_TECH", "測試科技業", "FAKE_TWSE"),
                source_code="FAKE_TWSE",
                as_of=now,
                received_at=now,
                data_status=DataStatus.FINAL,
            ),
            SecurityRecord(
                market=MarketCode.TPEX,
                code="5678",
                name="範例電子",
                security_type=SecurityType.COMMON_STOCK,
                status=SecurityStatus.ACTIVE,
                listing_date=None,
                industry=Industry("TEST_ELEC", "測試電子業", "FAKE_TPEX"),
                source_code="FAKE_TPEX",
                as_of=now,
                received_at=now,
                data_status=DataStatus.FINAL,
            ),
        ]

    async def get_daily_prices(
        self,
        trade_date: date | None = None,
        security: SecurityKey | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceRecord]:
        end = end_date or trade_date or date(2026, 8, 7)
        start = start_date or (end if trade_date else end - timedelta(days=520))
        keys = [SecurityKey(MarketCode.TWSE, "1234"), SecurityKey(MarketCode.TPEX, "5678")]
        if security is not None:
            keys = [security]
        result: list[DailyPriceRecord] = []
        current = start
        sequence = 0
        while current <= end:
            if current.weekday() < 5:
                for offset, key in enumerate(keys):
                    base = Decimal("40") + Decimal(sequence) / Decimal("10") + Decimal(offset * 10)
                    adjusted_factor = Decimal("0.95")
                    timestamp = datetime.combine(current, datetime.min.time(), tzinfo=UTC)
                    result.append(
                        DailyPriceRecord(
                            security=key,
                            trade_date=current,
                            open=base,
                            high=base + 2,
                            low=base - 1,
                            close=base + 1,
                            adjusted_open=base * adjusted_factor,
                            adjusted_high=(base + 2) * adjusted_factor,
                            adjusted_low=(base - 1) * adjusted_factor,
                            adjusted_close=(base + 1) * adjusted_factor,
                            volume_shares=100_000 + sequence * 100,
                            turnover_amount=(base + 1) * Decimal(100_000 + sequence * 100),
                            source_code=f"FAKE_{key.market.value}_DAILY",
                            as_of=timestamp,
                            received_at=timestamp + timedelta(hours=8),
                            data_status=DataStatus.FINAL,
                            source_revision="fixture-v1",
                        )
                    )
                sequence += 1
            current += timedelta(days=1)
        return result

    source_code = "FAKE_MARKET_SPOT"

    @staticmethod
    def _metadata(trade_date: date, market: MarketCode) -> SourceMetadata:
        timestamp = datetime.combine(trade_date, datetime.min.time(), tzinfo=UTC)
        return SourceMetadata(
            f"FAKE_{market.value}_SPOT",
            timestamp,
            timestamp + timedelta(hours=8),
            DataStatus.FINAL,
            "fixture-v1",
        )

    async def get_market_indexes(self, trade_date: date) -> list[MarketIndexRecord]:
        day = Decimal((trade_date - date(2026, 1, 1)).days)
        return [
            MarketIndexRecord(
                code,
                name,
                market,
                trade_date,
                base + day,
                base + day + 80,
                base + day - 60,
                base + day + 25,
                Decimal(25),
                Decimal("0.12"),
                Decimal("320000000000") + day * 1000000,
                8_000_000_000 + int(day) * 1000,
                self._metadata(trade_date, market),
            )
            for code, name, market, base in (
                ("TAIEX", "加權指數", MarketCode.TWSE, Decimal(22000)),
                ("OTC", "櫃買指數", MarketCode.TPEX, Decimal(260)),
            )
        ]

    async def get_market_breadth(self, trade_date: date) -> list[MarketBreadthRecord]:
        return [
            MarketBreadthRecord(
                market,
                trade_date,
                500 - offset,
                350 + offset,
                100,
                25,
                8,
                950,
                Decimal("320000000000") - offset * 100000000,
                self._metadata(trade_date, market),
            )
            for offset, market in enumerate(MarketCode)
        ]

    def _institutional(
        self, trade_date: date, security: SecurityKey | None
    ) -> list[InstitutionalRecord]:
        markets = [security.market] if security else list(MarketCode)
        result = []
        for market in markets:
            multiplier = Decimal(1 if market is MarketCode.TWSE else 2)
            rows = (
                (InstitutionType.FOREIGN, None, 120, 100),
                (InstitutionType.INVESTMENT_TRUST, None, 45, 35),
                (InstitutionType.DEALER, DealerSubtype.PROPRIETARY, 20, 18),
                (InstitutionType.DEALER, DealerSubtype.HEDGE, 30, 35),
                (InstitutionType.DEALER, DealerSubtype.TOTAL, 50, 53),
                (InstitutionType.TOTAL, None, 215, 188),
            )
            for kind, subtype, buy, sell in rows:
                if security:
                    buy_value, sell_value = (
                        int(Decimal(buy * 1000) * multiplier),
                        int(Decimal(sell * 1000) * multiplier),
                    )
                else:
                    buy_value, sell_value = (
                        Decimal(buy * 1_000_000_000) * multiplier,
                        Decimal(sell * 1_000_000_000) * multiplier,
                    )
                result.append(
                    InstitutionalRecord(
                        market,
                        trade_date,
                        kind,
                        subtype,
                        buy_value,
                        sell_value,
                        buy_value - sell_value,
                        self._metadata(trade_date, market),
                        security,
                        not bool(security),
                    )
                )
        return result

    async def get_market_institutional_spot(self, trade_date: date) -> list[InstitutionalRecord]:
        return self._institutional(trade_date, None)

    async def get_security_institutional_spot(self, trade_date: date) -> list[InstitutionalRecord]:
        return self._institutional(
            trade_date, SecurityKey(MarketCode.TWSE, "1234")
        ) + self._institutional(trade_date, SecurityKey(MarketCode.TPEX, "5678"))

    def _margins(self, trade_date: date, security: bool) -> list[MarginRecord]:
        keys = (
            [SecurityKey(MarketCode.TWSE, "1234"), SecurityKey(MarketCode.TPEX, "5678")]
            if security
            else [None, None]
        )
        return [
            MarginRecord(
                market,
                trade_date,
                120000,
                100000,
                1000,
                8_000_000,
                19000,
                30000,
                25000,
                500,
                800000,
                4500,
                Decimal("10.0"),
                self._metadata(trade_date, market),
                key,
                Decimal("55.0") if key else None,
                Decimal("15.0") if key else None,
            )
            for market, key in zip(MarketCode, keys, strict=True)
        ]

    async def get_market_margin_trading(self, trade_date: date) -> list[MarginRecord]:
        return self._margins(trade_date, False)

    async def get_security_margin_trading(self, trade_date: date) -> list[MarginRecord]:
        return self._margins(trade_date, True)

    def _lending(self, trade_date: date, security: bool) -> list[LendingRecord]:
        keys = (
            [SecurityKey(MarketCode.TWSE, "1234"), SecurityKey(MarketCode.TPEX, "5678")]
            if security
            else [None, None]
        )
        return [
            LendingRecord(
                market,
                trade_date,
                50000,
                15000,
                2_000_000,
                35000,
                self._metadata(trade_date, market),
                key,
            )
            for market, key in zip(MarketCode, keys, strict=True)
        ]

    async def get_market_securities_lending(self, trade_date: date) -> list[LendingRecord]:
        return self._lending(trade_date, False)

    async def get_security_securities_lending(self, trade_date: date) -> list[LendingRecord]:
        return self._lending(trade_date, True)
