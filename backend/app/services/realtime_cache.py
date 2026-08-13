import json
import logging

from redis.asyncio import Redis

from app.domain.realtime import RealtimeQuote

logger = logging.getLogger(__name__)

CHANNEL_REALTIME_QUOTES = "realtime:quotes"
KEY_PREFIX_QUOTE = "realtime:quote:"


class RealtimeCacheService:
    def __init__(self, redis: Redis, default_ttl_seconds: int = 120):
        self.redis = redis
        self.default_ttl = default_ttl_seconds

    def _get_key(self, market: str, code: str) -> str:
        return f"{KEY_PREFIX_QUOTE}{market.upper()}:{code.upper()}"

    async def get_quote(self, market: str, code: str) -> RealtimeQuote | None:
        key = self._get_key(market, code)
        data = await self.redis.get(key)
        if not data:
            return None
        try:
            raw = json.loads(data)
            return RealtimeQuote.model_validate(raw)
        except Exception as e:
            logger.error(f"Failed to parse cached quote for {key}: {e}")
            return None

    async def get_quotes_batch(
        self, targets: list[dict[str, str]]
    ) -> list[RealtimeQuote | None]:
        if not targets:
            return []
        keys = [self._get_key(t.get("market", ""), t.get("code", "")) for t in targets]
        results = await self.redis.mget(keys)
        quotes: list[RealtimeQuote | None] = []
        for raw_val in results:
            if not raw_val:
                quotes.append(None)
                continue
            try:
                quotes.append(RealtimeQuote.model_validate_json(raw_val))
            except Exception:
                quotes.append(None)
        return quotes

    async def save_and_publish_quote(self, quote: RealtimeQuote) -> bool:
        """Saves quote if newer than cached, then publishes to Redis channel."""
        key = self._get_key(quote.market_id, quote.code)
        existing = await self.get_quote(quote.market_id, quote.code)

        if existing is not None:
            # Deterministic ordering check: sequence first, then exchange_timestamp
            if quote.sequence is not None and existing.sequence is not None:
                if quote.sequence <= existing.sequence:
                    logger.debug(f"Ignoring stale sequence quote for {key}")
                    return False
            elif quote.exchange_timestamp <= existing.exchange_timestamp:
                logger.debug(f"Ignoring older exchange_timestamp quote for {key}")
                return False

        serialized = quote.model_dump_json()

        # Save to Redis with TTL
        await self.redis.set(key, serialized, ex=self.default_ttl)

        # Publish event to channel for WebSocket Hub distribution
        await self.redis.publish(CHANNEL_REALTIME_QUOTES, serialized)
        return True
