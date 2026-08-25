import asyncio
import logging
from collections import defaultdict

from app.adapters.realtime_base import RealtimeMarketDataProvider
from app.domain.realtime import ProviderCapabilities, RealtimeQuoteType
from app.services.intraday_candle_aggregator import IntradayCandleAggregator
from app.services.realtime_alerts import RealtimeAlertEvaluationService
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_capacity import RealtimeCapacityError, RealtimeSubscriptionError
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
        subscription_budget: int | None = None,
    ):
        self.provider = provider
        self.cache_service = cache_service
        self.hub = hub
        self.aggregator = aggregator
        self.taxonomy_aggregator = taxonomy_aggregator
        self.alert_evaluator = alert_evaluator
        self.subscription_budget = subscription_budget
        self.provider_hard_limit: int | None = None
        self.capacity_rejections = 0
        self._ingestion_task: asyncio.Task | None = None
        self._running = False
        self.reconnect_count = 0
        self._subscription_owners: dict[tuple[str, RealtimeQuoteType], set[str]] = defaultdict(set)
        self._subscription_lock = asyncio.Lock()

    async def acquire_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        capabilities = await self.provider.get_capabilities()
        if not capabilities.configured:
            raise RealtimeSubscriptionError("Realtime provider is unconfigured")
        identity = (security_key.upper(), quote_type)
        async with self._subscription_lock:
            owners = self._subscription_owners.get(identity)
            if owners is not None and owner in owners:
                return
            first = not owners
            if first:
                limit = self._effective_limit(capabilities)
                if limit is not None and len(self._subscription_owners) >= limit:
                    self.capacity_rejections += 1
                    raise RealtimeCapacityError(
                        f"Realtime broker subscription capacity reached ({limit})"
                    )
                owners = self._subscription_owners[identity]
            owners.add(owner)
            if first:
                broker_owner = f"manager:{identity[0]}:{quote_type.value}"
                try:
                    await self.provider.acquire_subscription(
                        broker_owner, identity[0], quote_type
                    )
                except Exception as error:
                    owners.remove(owner)
                    if not owners:
                        del self._subscription_owners[identity]
                    raise RealtimeSubscriptionError("Provider subscription failed") from error

    async def release_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        identity = (security_key.upper(), quote_type)
        async with self._subscription_lock:
            owners = self._subscription_owners.get(identity)
            if not owners or owner not in owners:
                return
            owners.remove(owner)
            if owners:
                return
            broker_owner = f"manager:{identity[0]}:{quote_type.value}"
            try:
                await self.provider.release_subscription(broker_owner, identity[0], quote_type)
            except Exception as error:
                owners.add(owner)
                raise RealtimeSubscriptionError("Provider unsubscription failed") from error
            del self._subscription_owners[identity]

    async def start(self):
        capabilities = await self.provider.get_capabilities()
        self._validate_budget(capabilities)
        self.provider_hard_limit = capabilities.subscription_hard_limit
        self._running = True
        self.hub.provider_status = (
            "CONNECTED"
            if capabilities.is_live_eligible and capabilities.source_type != "FAKE_SIMULATOR"
            else "SIMULATED"
            if capabilities.source_type == "FAKE_SIMULATOR"
            else "CONFIGURED / DISCONNECTED"
            if capabilities.configured
            else "UNCONFIGURED"
        )
        if self.alert_evaluator is not None:
            self.alert_evaluator.provider_status = (
                "FAKE"
                if self.hub.provider_status == "SIMULATED"
                else "LIVE"
                if self.hub.provider_status == "CONNECTED"
                else self.hub.provider_status
            )
        logger.info(
            f"Starting RealtimeProviderManager with provider '{capabilities.provider_name}' "
            f"(License: {capabilities.license_status})"
        )
        if capabilities.realtime_available or capabilities.configured:
            self._ingestion_task = asyncio.create_task(self._ingestion_loop())
        else:
            logger.info("Realtime ingestion loop skipped (provider unavailable/unconfigured)")

    async def stop(self):
        self._running = False
        if self._ingestion_task:
            self._ingestion_task.cancel()
        await self.provider.close()
        logger.info("Stopped RealtimeProviderManager")

    async def get_capabilities(self) -> ProviderCapabilities:
        return await self.provider.get_capabilities()

    def capacity_status(self) -> dict[str, int | None]:
        limit = self.subscription_budget or self.provider_hard_limit
        active = len(self._subscription_owners)
        return {
            "budget": self.subscription_budget,
            "provider_hard_limit": self.provider_hard_limit,
            "active_resources": active,
            "remaining_slots": max(limit - active, 0) if limit is not None else None,
            "capacity_rejections": self.capacity_rejections,
        }

    def _effective_limit(self, capabilities: ProviderCapabilities) -> int | None:
        self._validate_budget(capabilities)
        self.provider_hard_limit = capabilities.subscription_hard_limit
        return self.subscription_budget or capabilities.subscription_hard_limit

    def _validate_budget(self, capabilities: ProviderCapabilities) -> None:
        hard_limit = capabilities.subscription_hard_limit
        if (
            self.subscription_budget is not None
            and hard_limit is not None
            and self.subscription_budget > hard_limit
        ):
            raise RealtimeCapacityError(
                f"Configured realtime budget exceeds provider hard limit ({hard_limit})"
            )

    async def _ingestion_loop(self):
        while self._running:
            try:
                async for quote in self.provider.stream_quotes():
                    if not self._running:
                        break
                    capabilities = await self.provider.get_capabilities()
                    if capabilities.is_live_eligible:
                        self.hub.provider_status = "CONNECTED"
                        if self.alert_evaluator is not None:
                            self.alert_evaluator.provider_status = "LIVE"
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
                self.hub.provider_status = "CONFIGURED / DISCONNECTED"
                if self.alert_evaluator is not None:
                    self.alert_evaluator.provider_status = "CONFIGURED / DISCONNECTED"
                await asyncio.sleep(2.0)
