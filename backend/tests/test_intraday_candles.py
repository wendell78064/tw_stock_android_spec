from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from app.domain.realtime import DataStatus, IntradayInterval, RealtimeEventKind, RealtimeQuote
from app.main import app
from app.services.intraday_candle_aggregator import IntradayCandleAggregator
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub


class CandleRedis:
    def __init__(self):
        self.values = {}
        self.sorted = {}
        self.published = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def mget(self, keys):
        return [self.values.get(key) for key in keys]

    async def delete(self, key):
        self.values.pop(key, None)

    async def expire(self, key, seconds):
        return True

    async def publish(self, channel, value):
        self.published.append((channel, value))

    async def zadd(self, key, mapping):
        self.sorted.setdefault(key, {}).update(mapping)

    async def zrem(self, key, *members):
        for member in members:
            self.sorted.get(key, {}).pop(member, None)

    async def zremrangebyscore(self, key, minimum, maximum):
        return 0

    async def zrangebyscore(self, key, minimum, maximum):
        low = float("-inf") if minimum == "-inf" else float(minimum)
        high = float("inf") if maximum == "+inf" else float(maximum)
        return [
            member
            for member, score in sorted(self.sorted.get(key, {}).items(), key=lambda item: item[1])
            if low <= score <= high
        ]


def quote(timestamp, price, volume, sequence, *, event_kind=RealtimeEventKind.UPDATE):
    return RealtimeQuote(
        security_id="sec_1234",
        market_id="TWSE",
        code="1234",
        exchange_timestamp=timestamp,
        received_at=timestamp + timedelta(milliseconds=10),
        last_price=Decimal(price),
        total_volume=volume,
        sequence=sequence,
        data_status=DataStatus.LIVE,
        provider="FAKE_REALTIME_PROVIDER",
        event_kind=event_kind,
    )


@pytest.mark.asyncio
async def test_quote_aggregation_ohlcv_finalization_and_five_minute():
    redis = CandleRedis()
    cache = RealtimeCacheService(redis)
    aggregator = IntradayCandleAggregator(cache)
    base = datetime(2026, 8, 13, 1, 0, 5, tzinfo=UTC)
    await aggregator.accept(quote(base, "100", 1000, 1, event_kind=RealtimeEventKind.SNAPSHOT))
    for seconds, price, volume, sequence in (
        (15, "100", 1010, 2),
        (35, "102", 1020, 3),
        (50, "99", 1030, 4),
        (55, "101", 1040, 5),
    ):
        await aggregator.accept(quote(base.replace(second=seconds), price, volume, sequence))
    await aggregator.accept(quote(base + timedelta(minutes=1), "103", 1050, 6))
    one = await cache.get_candles(IntradayInterval.ONE_MINUTE, "TWSE", "1234")
    assert (one[0].open, one[0].high, one[0].low, one[0].close) == tuple(
        map(Decimal, ("100", "102", "99", "101"))
    )
    assert one[0].volume == 40 and one[0].is_final
    assert one[1].close == Decimal("103") and not one[1].is_final
    five = await cache.get_candles(IntradayInterval.FIVE_MINUTES, "TWSE", "1234")
    assert five[-1].high == Decimal("103") and five[-1].volume == 50


@pytest.mark.asyncio
async def test_reset_duplicate_and_timezone_bucket():
    redis = CandleRedis()
    cache = RealtimeCacheService(redis)
    aggregator = IntradayCandleAggregator(cache)
    timestamp = datetime(2026, 8, 13, 1, 4, 59, tzinfo=UTC)
    await aggregator.accept(
        quote(timestamp, "100.01", 100, 1, event_kind=RealtimeEventKind.SNAPSHOT)
    )
    await aggregator.accept(quote(timestamp, "100.02", 90, 2))
    assert aggregator.metrics["volume_reset_detected"] == 1
    assert (await cache.get_candles(IntradayInterval.ONE_MINUTE, "TWSE", "1234"))[-1].volume == 0
    assert await aggregator.accept(quote(timestamp - timedelta(seconds=1), "999", 91, 1)) == []
    start, _ = aggregator.bucket(timestamp, IntradayInterval.FIVE_MINUTES)
    assert start == datetime(2026, 8, 13, 1, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_session_close_and_websocket_initial_snapshot():
    redis = CandleRedis()
    cache = RealtimeCacheService(redis)
    aggregator = IntradayCandleAggregator(cache)
    timestamp = datetime(2026, 8, 13, 1, 0, tzinfo=UTC)
    await aggregator.accept(quote(timestamp, "100", 100, 1, event_kind=RealtimeEventKind.SNAPSHOT))
    await aggregator.accept(quote(timestamp + timedelta(seconds=5), "101", 110, 2))
    session = (await cache.get_candles(IntradayInterval.ONE_MINUTE, "TWSE", "1234"))[0].session
    finalized = await aggregator.finalize_session(
        "TWSE", "1234", session, timestamp + timedelta(hours=5)
    )
    assert len(finalized) == 2 and all(candle.is_final for candle in finalized)

    hub = RealtimeQuoteHub(redis, cache)
    websocket = AsyncMock()
    connection = await hub.register_connection(websocket)
    await hub.handle_subscribe(connection, [{"market": "TWSE", "code": "1234"}], ["candle_1m"])
    messages = [call.args[0] for call in websocket.send_json.call_args_list]
    assert any(message["type"] == "candle_snapshot" for message in messages)


def test_intraday_http_history_and_invalid_interval():
    redis = CandleRedis()
    cache = RealtimeCacheService(redis)
    app.state.realtime_cache_service = cache
    client = TestClient(app)
    assert client.get("/v1/intraday/TWSE/1234/candles?interval=9m").status_code == 422
    response = client.get("/v1/intraday/TWSE/1234/candles?interval=1m")
    assert response.status_code == 200
    assert response.json()["interval"] == "1m"
    assert response.json()["data_status"] == "UNAVAILABLE"
