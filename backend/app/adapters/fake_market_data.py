from datetime import UTC, datetime

from app.domain.market_data import DataStatus, MarketSnapshot


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

