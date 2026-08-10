from datetime import UTC, datetime

from app.domain.market_data import DataStatus, MarketSnapshot
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
