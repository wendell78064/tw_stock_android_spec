import asyncio
import logging
from app.adapters.fake_realtime_provider import FakeRealtimeProvider, UnconfiguredRealtimeProvider
from app.adapters.realtime_base import RealtimeMarketDataProvider
from app.domain.realtime import ProviderCapabilities, RealtimeQuote
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub

logger = logging.getLogger(__name__)


class RealtimeProviderManager:
    def __init__(
        self,
        provider: RealtimeMarketDataProvider,
        cache_service: RealtimeCacheService,
        hub: RealtimeQuoteHub,
    ):
        self.provider = provider
        self.cache_service = cache_service
        self.hub = hub
        self._ingestion_task: asyncio.Task | None = None
        self._running = False
        self.reconnect_count = 0

    async def start(self):
        self._running = True
        capabilities = await self.provider.get_capabilities()
        logger.info(
            f"Starting RealtimeProviderManager with provider '{capabilities.provider_name}' "
            f"(License: {capabilities.license_status})"
        )
        self._ingestion_task = asyncio.create_task(self._ingestion_loop())

    async def stop(self):
        self._running = False
        if self._ingestion_task:
            self._ingestion_task.cancel()
        await self.provider.close()
        logger.info("Stopped RealtimeProviderManager")

    async def get_capabilities(self) -> ProviderCapabilities:
        return await self.provider.get_capabilities()

    async def _ingestion_loop(self):
        while self._running:
            try:
                async for quote in self.provider.stream_quotes():
                    if not self._running:
                        break
                    # Save to Redis and publish to hub
                    await self.cache_service.save_and_publish_quote(quote)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in realtime ingestion loop: {e}")
                self.reconnect_count += 1
                await asyncio.sleep(2.0)
