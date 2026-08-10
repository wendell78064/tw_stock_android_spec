from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.market_data import DataStatus, MarketSnapshot
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
