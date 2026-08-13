import asyncio
import logging

from app.adapters.realtime_base import RealtimeMarketDataProvider
from app.domain.realtime import ProviderCapabilities
from app.services.intraday_candle_aggregator import IntradayCandleAggregator
from app.services.realtime_alerts import RealtimeAlertEvaluationService
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_strength import RealtimeTaxonomyAggregator

logger = logging.getLogger(__name__)


class RealtimeProviderManager:
    def __init__(
        self,
        provider: RealtimeMarketDataProvider,
        cache_service: RealtimeCacheService,
        hub: RealtimeQuoteHub,
        aggregator: IntradayCandleAggregator | None = None,
        taxonomy_aggregator: RealtimeTaxonomyAggregator | None = None,
        alert_evaluator: RealtimeAlertEvaluationService | None = None,
    ):
        self.provider = provider
        self.cache_service = cache_service
        self.hub = hub
        self.aggregator = aggregator
        self.taxonomy_aggregator = taxonomy_aggregator
        self.alert_evaluator = alert_evaluator
        self._ingestion_task: asyncio.Task | None = None
        self._running = False
        self.reconnect_count = 0

    async def start(self):
        self._running = True
        capabilities = await self.provider.get_capabilities()
        self.hub.provider_status = (
            "LIVE"
            if capabilities.is_live_eligible and capabilities.source_type != "FAKE_SIMULATOR"
            else "SIMULATED"
            if capabilities.source_type == "FAKE_SIMULATOR"
            else "UNAVAILABLE"
        )
        if self.alert_evaluator is not None:
            self.alert_evaluator.provider_status = (
                "FAKE" if self.hub.provider_status == "SIMULATED" else self.hub.provider_status
            )
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
                    saved = await self.cache_service.save_and_publish_quote(quote)
                    if saved and self.aggregator is not None:
                        await self.aggregator.accept(quote)
                    if saved and self.taxonomy_aggregator is not None:
                        await self.taxonomy_aggregator.accept(quote)
                    if saved and self.alert_evaluator is not None:
                        await self.alert_evaluator.accept(quote)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in realtime ingestion loop: {e}")
                self.reconnect_count += 1
                await asyncio.sleep(2.0)
