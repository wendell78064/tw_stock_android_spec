import json
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from redis.asyncio import Redis

from app.domain.realtime import IntradayCandle, IntradayInterval, RealtimeQuote, TradingSession

logger = logging.getLogger(__name__)

CHANNEL_REALTIME_QUOTES = "realtime:quotes"
KEY_PREFIX_QUOTE = "realtime:quote:"
CHANNEL_INTRADAY_CANDLES = "realtime:candles"
KEY_PREFIX_CANDLE = "intraday:candles:"
KEY_PREFIX_CURRENT = "intraday:current:"
KEY_PREFIX_BASELINE = "intraday:baseline:"


class RealtimeCacheService:
    def __init__(
        self, redis: Redis, default_ttl_seconds: int = 120, intraday_retention_days: int = 5
    ):
        self.redis = redis
        self.default_ttl = default_ttl_seconds
        self.intraday_retention_days = intraday_retention_days

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

    async def get_quotes_batch(self, targets: list[dict[str, str]]) -> list[RealtimeQuote | None]:
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

    def _candle_key(
        self, interval: IntradayInterval, market: str, code: str, session: TradingSession
    ) -> str:
        return (
            f"{KEY_PREFIX_CANDLE}{interval.value}:{market.upper()}:{code.upper()}:{session.value}"
        )

    def _current_key(
        self, interval: IntradayInterval, market: str, code: str, session: TradingSession
    ) -> str:
        return (
            f"{KEY_PREFIX_CURRENT}{interval.value}:{market.upper()}:{code.upper()}:{session.value}"
        )

    async def save_candle(self, candle: IntradayCandle, publish: bool = True) -> None:
        payload = candle.model_dump_json()
        score = candle.bucket_start.timestamp()
        history = self._candle_key(candle.interval, candle.market_id, candle.code, candle.session)
        current = self._current_key(candle.interval, candle.market_id, candle.code, candle.session)
        member_prefix = f"{candle.bucket_start.isoformat()}|"
        existing = await self.redis.zrangebyscore(history, score, score)
        if existing:
            await self.redis.zrem(history, *existing)
        await self.redis.zadd(history, {member_prefix + payload: score})
        cutoff = (datetime.now(UTC) - timedelta(days=self.intraday_retention_days + 2)).timestamp()
        await self.redis.zremrangebyscore(history, "-inf", cutoff)
        await self.redis.expire(history, (self.intraday_retention_days + 2) * 86400)
        if candle.is_final:
            await self.redis.delete(current)
        else:
            await self.redis.set(current, payload, ex=86400)
        if publish:
            await self.redis.publish(CHANNEL_INTRADAY_CANDLES, payload)

    async def get_current_candle(
        self, interval: IntradayInterval, market: str, code: str, session: TradingSession
    ) -> IntradayCandle | None:
        raw = await self.redis.get(self._current_key(interval, market, code, session))
        return IntradayCandle.model_validate_json(raw) if raw else None

    async def get_candles(
        self,
        interval: IntradayInterval,
        market: str,
        code: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[IntradayCandle]:
        keys = [self._candle_key(interval, market, code, session) for session in TradingSession]
        minimum = start.timestamp() if start else "-inf"
        maximum = end.timestamp() if end else "+inf"
        rows: list[IntradayCandle] = []
        for key in keys:
            values = await self.redis.zrangebyscore(key, minimum, maximum)
            rows.extend(IntradayCandle.model_validate_json(v.split("|", 1)[1]) for v in values)
        return sorted(rows, key=lambda c: c.bucket_start)[-limit:]

    async def get_volume_baseline(self, quote: RealtimeQuote) -> tuple[int, Decimal | None] | None:
        raw = await self.redis.get(
            f"{KEY_PREFIX_BASELINE}{quote.market_id.upper()}:{quote.code.upper()}:{quote.session.value}"
        )
        if not raw:
            return None
        value = json.loads(raw)
        return int(value["volume"]), Decimal(value["turnover"]) if value[
            "turnover"
        ] is not None else None

    async def set_volume_baseline(self, quote: RealtimeQuote) -> None:
        value = {
            "volume": quote.total_volume,
            "turnover": str(quote.turnover_amount) if quote.turnover_amount is not None else None,
        }
        await self.redis.set(
            f"{KEY_PREFIX_BASELINE}{quote.market_id.upper()}:{quote.code.upper()}:{quote.session.value}",
            json.dumps(value),
            ex=86400,
        )
