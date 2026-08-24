import asyncio
import json
import logging
from collections import defaultdict
from typing import Protocol

from fastapi import WebSocket
from redis.asyncio import Redis

from app.domain.realtime import (
    IntradayCandle,
    IntradayInterval,
    RealtimeQuote,
    RealtimeQuoteType,
)
from app.domain.realtime_strength import RealtimeTaxonomyType
from app.services.realtime_alerts import REALTIME_ALERT_CHANNEL
from app.services.realtime_cache import (
    CHANNEL_INTRADAY_CANDLES,
    CHANNEL_REALTIME_INDUSTRY,
    CHANNEL_REALTIME_MARKET,
    CHANNEL_REALTIME_QUOTES,
    CHANNEL_REALTIME_THEME,
    RealtimeCacheService,
)

logger = logging.getLogger(__name__)


class SubscriptionManager(Protocol):
    async def acquire_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None: ...

    async def release_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None: ...


class ConnectionSession:
    def __init__(self, websocket: WebSocket, max_subscriptions: int = 100):
        self.websocket = websocket
        self.max_subscriptions = max_subscriptions
        self.subscriptions: set[str] = set()  # "MARKET:CODE"
        self.provider_subscriptions: set[tuple[str, RealtimeQuoteType]] = set()
        self.owner_id = f"ws:{id(self)}"
        self.channels: set[str] = {"quote"}
        self._pending_coalesced: dict[str, RealtimeQuote] = {}
        self.is_alive = True


class RealtimeQuoteHub:
    def __init__(
        self,
        redis: Redis,
        cache_service: RealtimeCacheService,
        max_subscriptions_per_conn: int = 100,
        subscription_manager: SubscriptionManager | None = None,
    ):
        self.redis = redis
        self.cache_service = cache_service
        self.max_subscriptions_per_conn = max_subscriptions_per_conn
        self.subscription_manager = subscription_manager
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
        if self.subscription_manager is not None:
            for key, quote_type in list(session.provider_subscriptions):
                await self.subscription_manager.release_subscription(
                    session.owner_id, key, quote_type
                )
        session.provider_subscriptions.clear()
        for key in list(session.subscriptions):
            self.key_to_sessions[key].discard(session)
            if not self.key_to_sessions[key]:
                del self.key_to_sessions[key]
        logger.info(f"Unregistered WS connection. Remaining connections: {len(self.sessions)}")

    async def handle_subscribe(
        self,
        session: ConnectionSession,
        targets: list[dict[str, str]],
        channels: list[str] | None = None,
    ):
        session.channels = set(channels or ["quote"]) & {
            "quote",
            "candle_1m",
            "candle_5m",
            "market",
            "industry_strength",
            "theme_strength",
            "alert",
        }
        added_keys: list[str] = []
        for t in targets:
            market = t.get("market", "").upper()
            code = t.get("code", "").upper()
            if not self._valid_security_target(market, code):
                await session.websocket.send_json(
                    {
                        "type": "error",
                        "version": 1,
                        "message": "market must be TWSE/TPEX and code must be 4 to 6 digits",
                    }
                )
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

            quote_types = self._quote_types(t)
            if self.subscription_manager is not None:
                for quote_type in quote_types:
                    identity = (key, quote_type)
                    if identity not in session.provider_subscriptions:
                        await self.subscription_manager.acquire_subscription(
                            session.owner_id, key, quote_type
                        )
                        session.provider_subscriptions.add(identity)
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
                if q and "quote" in session.channels:
                    await session.websocket.send_json(
                        {
                            "type": "snapshot",
                            "version": 1,
                            "data": q.model_dump(mode="json"),
                        }
                    )
            for key in added_keys:
                market, code = key.split(":", 1)
                for interval, channel in (
                    (IntradayInterval.ONE_MINUTE, "candle_1m"),
                    (IntradayInterval.FIVE_MINUTES, "candle_5m"),
                ):
                    if channel in session.channels:
                        candles = await self.cache_service.get_candles(
                            interval, market, code, limit=500
                        )
                        await session.websocket.send_json(
                            {
                                "type": "candle_snapshot",
                                "version": 1,
                                "interval": interval.value,
                                "data": [c.model_dump(mode="json") for c in candles],
                            }
                        )
        if "market" in session.channels:
            markets = [
                await self.cache_service.get_market_snapshot(market) for market in ("TWSE", "TPEx")
            ]
            await session.websocket.send_json(
                {
                    "type": "market_snapshot",
                    "version": 1,
                    "data": [item.model_dump(mode="json") for item in markets if item],
                }
            )
        for channel, taxonomy_type in (
            ("industry_strength", RealtimeTaxonomyType.INDUSTRY),
            ("theme_strength", RealtimeTaxonomyType.THEME),
        ):
            if channel in session.channels:
                ranking = await self.cache_service.get_taxonomy_ranking(taxonomy_type)
                await session.websocket.send_json(
                    {
                        "type": "taxonomy_ranking_snapshot",
                        "version": 1,
                        "taxonomy_type": taxonomy_type.value,
                        "data": [item.model_dump(mode="json") for item in ranking],
                    }
                )

    async def handle_unsubscribe(self, session: ConnectionSession, targets: list[dict[str, str]]):
        for t in targets:
            market = t.get("market", "").upper()
            code = t.get("code", "").upper()
            if not self._valid_security_target(market, code):
                await session.websocket.send_json(
                    {
                        "type": "error",
                        "version": 1,
                        "message": "market must be TWSE/TPEX and code must be 4 to 6 digits",
                    }
                )
                continue
            key = f"{market}:{code}"
            requested = set(self._quote_types(t)) if self._has_quote_type(t) else {
                quote_type
                for subscribed_key, quote_type in session.provider_subscriptions
                if subscribed_key == key
            }
            if self.subscription_manager is not None:
                for quote_type in requested:
                    identity = (key, quote_type)
                    if identity in session.provider_subscriptions:
                        await self.subscription_manager.release_subscription(
                            session.owner_id, key, quote_type
                        )
                        session.provider_subscriptions.discard(identity)
            if any(item[0] == key for item in session.provider_subscriptions):
                continue
            session.subscriptions.discard(key)
            if key in self.key_to_sessions:
                self.key_to_sessions[key].discard(session)
                if not self.key_to_sessions[key]:
                    del self.key_to_sessions[key]

    @staticmethod
    def _has_quote_type(target: dict[str, str]) -> bool:
        return "quote_type" in target or "quote_types" in target

    @staticmethod
    def _valid_security_target(market: str, code: str) -> bool:
        return market in {"TWSE", "TPEX"} and code.isdigit() and 4 <= len(code) <= 6

    @staticmethod
    def _quote_types(target: dict[str, str]) -> list[RealtimeQuoteType]:
        raw = target.get("quote_types") or [target.get("quote_type", "tick")]
        if isinstance(raw, str):
            raw = [raw]
        try:
            return list(dict.fromkeys(RealtimeQuoteType(str(item).lower()) for item in raw))
        except ValueError as error:
            raise ValueError("quote_type must be tick or bid_ask") from error

    async def _listen_redis_pubsub(self):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(
            CHANNEL_REALTIME_QUOTES,
            CHANNEL_INTRADAY_CANDLES,
            CHANNEL_REALTIME_MARKET,
            CHANNEL_REALTIME_INDUSTRY,
            CHANNEL_REALTIME_THEME,
            REALTIME_ALERT_CHANNEL,
        )
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    self.quotes_received += 1
                    try:
                        raw = message["data"]
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        channel = message.get("channel")
                        if channel in (CHANNEL_REALTIME_MARKET, CHANNEL_REALTIME_MARKET.encode()):
                            self._route_global("market", "market_update", json.loads(raw))
                        elif channel in (
                            CHANNEL_REALTIME_INDUSTRY,
                            CHANNEL_REALTIME_INDUSTRY.encode(),
                        ):
                            self._route_global(
                                "industry_strength", "taxonomy_detail_update", json.loads(raw)
                            )
                        elif channel in (CHANNEL_REALTIME_THEME, CHANNEL_REALTIME_THEME.encode()):
                            self._route_global(
                                "theme_strength", "taxonomy_detail_update", json.loads(raw)
                            )
                        elif channel in (REALTIME_ALERT_CHANNEL, REALTIME_ALERT_CHANNEL.encode()):
                            self._route_global("alert", "alert_event", json.loads(raw))
                        elif channel in (
                            CHANNEL_INTRADAY_CANDLES,
                            CHANNEL_INTRADAY_CANDLES.encode(),
                        ):
                            self._route_candle(IntradayCandle.model_validate_json(raw))
                        else:
                            self._route_quote(RealtimeQuote.model_validate_json(raw))
                    except Exception as e:
                        logger.error(f"Error parsing pubsub quote: {e}")
        except asyncio.CancelledError:
            await pubsub.unsubscribe(CHANNEL_REALTIME_QUOTES)

    def _route_quote(self, quote: RealtimeQuote):
        key = quote.composite_key
        target_sessions = self.key_to_sessions.get(key, set())
        for session in target_sessions:
            if session.is_alive and "quote" in session.channels:
                if key in session._pending_coalesced:
                    self.quotes_coalesced += 1
                session._pending_coalesced[key] = quote

    def _route_candle(self, candle: IntradayCandle):
        key = f"{candle.market_id.upper()}:{candle.code.upper()}"
        channel = "candle_1m" if candle.interval is IntradayInterval.ONE_MINUTE else "candle_5m"
        for session in self.key_to_sessions.get(key, set()):
            if session.is_alive and channel in session.channels:
                asyncio.create_task(
                    session.websocket.send_json(
                        {
                            "type": "candle",
                            "version": 1,
                            "interval": candle.interval.value,
                            "data": candle.model_dump(mode="json"),
                        }
                    )
                )

    def _route_global(self, channel: str, message_type: str, data: dict):
        for session in self.sessions:
            if session.is_alive and channel in session.channels:
                asyncio.create_task(
                    session.websocket.send_json(
                        {
                            "type": message_type,
                            "version": 1,
                            "as_of": data.get("as_of"),
                            "data_status": data.get("data_status"),
                            "data": data,
                        }
                    )
                )

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
