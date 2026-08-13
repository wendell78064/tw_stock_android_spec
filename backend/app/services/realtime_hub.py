import asyncio
from collections import defaultdict
import logging

from fastapi import WebSocket
from redis.asyncio import Redis

from app.domain.realtime import RealtimeQuote
from app.services.realtime_cache import CHANNEL_REALTIME_QUOTES, RealtimeCacheService

logger = logging.getLogger(__name__)


class ConnectionSession:
    def __init__(self, websocket: WebSocket, max_subscriptions: int = 100):
        self.websocket = websocket
        self.max_subscriptions = max_subscriptions
        self.subscriptions: set[str] = set()  # "MARKET:CODE"
        self._pending_coalesced: dict[str, RealtimeQuote] = {}
        self.is_alive = True


class RealtimeQuoteHub:
    def __init__(
        self,
        redis: Redis,
        cache_service: RealtimeCacheService,
        max_subscriptions_per_conn: int = 100,
    ):
        self.redis = redis
        self.cache_service = cache_service
        self.max_subscriptions_per_conn = max_subscriptions_per_conn
        self.sessions: set[ConnectionSession] = set()
        self.key_to_sessions: dict[str, set[ConnectionSession]] = defaultdict(set)
        self._pubsub_task: asyncio.Task | None = None
        self._dispatch_task: asyncio.Task | None = None
        self.provider_status: str = "LIVE"

        # Metrics counters
        self.quotes_received: int = 0
        self.quotes_published: int = 0
        self.quotes_deduplicated: int = 0
        self.quotes_coalesced: int = 0

    async def start(self):
        """Starts listening to Redis Pub/Sub channel for fanout distribution."""
        self._pubsub_task = asyncio.create_task(self._listen_redis_pubsub())
        self._dispatch_task = asyncio.create_task(self._coalesced_dispatch_loop())
        logger.info("RealtimeQuoteHub started")

    async def stop(self):
        """Stops background tasks."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._dispatch_task:
            self._dispatch_task.cancel()
        logger.info("RealtimeQuoteHub stopped")

    async def register_connection(self, websocket: WebSocket) -> ConnectionSession:
        session = ConnectionSession(websocket, self.max_subscriptions_per_conn)
        self.sessions.add(session)
        logger.info(f"Registered WS connection. Total connections: {len(self.sessions)}")
        return session

    async def unregister_connection(self, session: ConnectionSession):
        session.is_alive = False
        self.sessions.discard(session)
        for key in list(session.subscriptions):
            self.key_to_sessions[key].discard(session)
            if not self.key_to_sessions[key]:
                del self.key_to_sessions[key]
        logger.info(f"Unregistered WS connection. Remaining connections: {len(self.sessions)}")

    async def handle_subscribe(
        self, session: ConnectionSession, targets: list[dict[str, str]]
    ):
        added_keys: list[str] = []
        for t in targets:
            market = t.get("market", "").upper()
            code = t.get("code", "").upper()
            if not market or not code:
                continue
            key = f"{market}:{code}"
            if len(session.subscriptions) >= session.max_subscriptions:
                await session.websocket.send_json(
                    {
                        "type": "error",
                        "version": 1,
                        "message": f"Subscription limit reached ({session.max_subscriptions})",
                    }
                )
                break

            session.subscriptions.add(key)
            self.key_to_sessions[key].add(session)
            added_keys.append(key)

        # Immediate snapshot delivery from Redis
        if added_keys:
            parsed_targets = [
                {"market": k.split(":")[0], "code": k.split(":")[1]} for k in added_keys
            ]
            cached_quotes = await self.cache_service.get_quotes_batch(parsed_targets)
            for q in cached_quotes:
                if q:
                    await session.websocket.send_json(
                        {
                            "type": "snapshot",
                            "version": 1,
                            "data": q.model_dump(mode="json"),
                        }
                    )

    async def handle_unsubscribe(
        self, session: ConnectionSession, targets: list[dict[str, str]]
    ):
        for t in targets:
            market = t.get("market", "").upper()
            code = t.get("code", "").upper()
            key = f"{market}:{code}"
            session.subscriptions.discard(key)
            if key in self.key_to_sessions:
                self.key_to_sessions[key].discard(session)
                if not self.key_to_sessions[key]:
                    del self.key_to_sessions[key]

    async def _listen_redis_pubsub(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(CHANNEL_REALTIME_QUOTES)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    self.quotes_received += 1
                    try:
                        raw = message["data"]
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        quote = RealtimeQuote.model_validate_json(raw)
                        self._route_quote(quote)
                    except Exception as e:
                        logger.error(f"Error parsing pubsub quote: {e}")
        except asyncio.CancelledError:
            await pubsub.unsubscribe(CHANNEL_REALTIME_QUOTES)

    def _route_quote(self, quote: RealtimeQuote):
        key = quote.composite_key
        target_sessions = self.key_to_sessions.get(key, set())
        for session in target_sessions:
            if session.is_alive:
                if key in session._pending_coalesced:
                    self.quotes_coalesced += 1
                session._pending_coalesced[key] = quote

    async def _coalesced_dispatch_loop(self):
        """Flushes coalesced quotes to clients every 100ms to avoid overloading slow clients."""
        while True:
            await asyncio.sleep(0.1)
            for session in list(self.sessions):
                if not session.is_alive or not session._pending_coalesced:
                    continue
                pending = session._pending_coalesced
                session._pending_coalesced = {}

                for quote in pending.values():
                    try:
                        await session.websocket.send_json(
                            {
                                "type": "quote",
                                "version": 1,
                                "data": quote.model_dump(mode="json"),
                            }
                        )
                        self.quotes_published += 1
                    except Exception as e:
                        logger.error(f"Error sending quote to WS client: {e}")
                        session.is_alive = False
