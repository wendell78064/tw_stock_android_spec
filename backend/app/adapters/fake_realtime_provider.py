import asyncio
import random
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.adapters.realtime_base import RealtimeMarketDataProvider
from app.domain.realtime import (
    DataStatus,
    LicenseStatus,
    ProviderCapabilities,
    RealtimeQuote,
    TradingSession,
)


class FakeRealtimeProvider(RealtimeMarketDataProvider):
    """Deterministic fake provider for testing and offline development."""

    def __init__(self, seed: int = 42, update_interval: float = 0.5):
        self.seed = seed
        self.update_interval = update_interval
        self._subscribed: set[str] = set()
        self._running = False
        self._sequence_map: dict[str, int] = {}
        self._base_prices: dict[str, Decimal] = {
            "TWSE:2330": Decimal("950.00"),
            "TWSE:2317": Decimal("200.00"),
            "TWSE:2454": Decimal("1200.00"),
            "TPEx:6547": Decimal("180.00"),
        }
        self.is_connected = True
        self.force_stale = False

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_name="FAKE_REALTIME_PROVIDER",
            source_type="FAKE_SIMULATOR",
            realtime_available=True,
            delay_seconds=0,
            redistribution_allowed=True,
            license_status=LicenseStatus.AUTHORIZED,
            configured=True,
        )

    async def subscribe_quotes(self, security_keys: list[str]) -> None:
        for k in security_keys:
            self._subscribed.add(k.upper())
            if k.upper() not in self._base_prices:
                self._base_prices[k.upper()] = Decimal("100.00")

    async def unsubscribe_quotes(self, security_keys: list[str]) -> None:
        for k in security_keys:
            self._subscribed.discard(k.upper())

    async def stream_quotes(self) -> AsyncGenerator[RealtimeQuote, None]:
        self._running = True
        rng = random.Random(self.seed)

        while self._running:
            if not self.is_connected:
                await asyncio.sleep(0.2)
                continue

            subbed = list(self._subscribed)
            if not subbed:
                await asyncio.sleep(0.2)
                continue

            target_key = rng.choice(subbed)
            parts = target_key.split(":")
            market = parts[0]
            code = parts[1] if len(parts) > 1 else target_key

            seq = self._sequence_map.get(target_key, 0) + 1
            self._sequence_map[target_key] = seq

            base_price = self._base_prices.get(target_key, Decimal("100.00"))
            delta = Decimal(str(round(rng.uniform(-2.0, 2.0), 2)))
            cur_price = max(Decimal("1.00"), base_price + delta)
            self._base_prices[target_key] = cur_price

            prev_close = base_price
            change = cur_price - prev_close
            change_pct = (change / prev_close * Decimal("100")).quantize(Decimal("0.01"))

            now = datetime.now(UTC)
            # Fake data must never be represented as production LIVE.
            status = DataStatus.STALE if self.force_stale else DataStatus.DELAYED

            quote = RealtimeQuote(
                security_id=f"sec_{code}",
                market_id=market,
                code=code,
                exchange_timestamp=now - timedelta(milliseconds=100),
                received_at=now,
                last_price=cur_price,
                last_size=rng.randint(1, 10),
                open_price=base_price,
                high_price=max(base_price, cur_price),
                low_price=min(base_price, cur_price),
                previous_close=prev_close,
                total_volume=seq * 10,
                turnover_amount=cur_price * Decimal(str(seq * 10)),
                bid_price=cur_price - Decimal("0.50"),
                bid_size=5,
                ask_price=cur_price + Decimal("0.50"),
                ask_size=5,
                change=change,
                change_percent=change_pct,
                session=TradingSession.REGULAR,
                sequence=seq,
                data_status=status,
                provider="FAKE_REALTIME_PROVIDER",
                delay_seconds=0,
            )
            yield quote
            await asyncio.sleep(self.update_interval)

    async def health(self) -> bool:
        return self.is_connected

    async def close(self) -> None:
        self._running = False


class UnconfiguredRealtimeProvider(RealtimeMarketDataProvider):
    """Placeholder when no official provider credentials are present."""

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_name="UNCONFIGURED_PRODUCTION_PROVIDER",
            source_type="NONE",
            realtime_available=False,
            delay_seconds=0,
            redistribution_allowed=False,
            license_status=LicenseStatus.UNCONFIGURED,
            configured=False,
            last_error="No realtime credentials configured",
        )

    async def subscribe_quotes(self, security_keys: list[str]) -> None:
        pass

    async def unsubscribe_quotes(self, security_keys: list[str]) -> None:
        pass

    async def stream_quotes(self) -> AsyncGenerator[RealtimeQuote, None]:
        try:
            while True:
                await asyncio.sleep(3600)
                if False:
                    yield
        except asyncio.CancelledError:
            return

    async def health(self) -> bool:
        return False

    async def close(self) -> None:
        pass
