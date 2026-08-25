import asyncio
import threading
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import shioaji as sj

from app.adapters.shioaji_realtime_provider import (
    ShioajiCallbackError,
    ShioajiProviderError,
    ShioajiRealtimeProvider,
    SubscriptionPriority,
)
from app.core.settings import Settings
from app.domain.realtime import DataStatus, LicenseStatus, RealtimeQuoteType
from app.services.realtime_provider_manager import RealtimeProviderManager


class FakeQuoteClient:
    def __init__(self, api):
        self.api = api
        self.subscriptions = []
        self.unsubscriptions = []
        self.emit_on_subscribe = None

    def subscribe(self, contract, quote_type):
        self.api.events.append(f"subscribe:{quote_type}")
        self.subscriptions.append((contract.code, quote_type))
        if self.emit_on_subscribe is not None:
            callback = (
                self.api.tick_callback
                if quote_type == "tick"
                else self.api.bidask_callback
            )
            callback(contract.exchange, self.emit_on_subscribe)

    def unsubscribe(self, contract, quote_type):
        self.unsubscriptions.append((contract.code, quote_type))


class FakeClient:
    def __init__(self):
        self.events = []
        self.tick_callback = None
        self.bidask_callback = None
        self.event_callback = None
        self.quote = FakeQuoteClient(self)
        self.contracts = SimpleNamespace(
            get=lambda code: {
                "2330": SimpleNamespace(code="2330", exchange="TSE"),
                "6488": SimpleNamespace(code="6488", exchange="OTC"),
            }.get(code)
        )
        self.login_calls = []

    def set_on_tick_stk_v1_callback(self, callback):
        self.events.append("register:tick")
        self.tick_callback = callback

    def set_on_bidask_stk_v1_callback(self, callback):
        self.events.append("register:bidask")
        self.bidask_callback = callback

    def set_event_callback(self, callback):
        self.events.append("register:event")
        self.event_callback = callback

    def login(self, **kwargs):
        self.login_calls.append(kwargs)

    def logout(self):
        pass


def make_provider(client=None):
    client = client or FakeClient()
    return ShioajiRealtimeProvider(
        "key", "secret", client_factory=lambda _simulation: client, reconnect_delays=(0,)
    )


@pytest.mark.asyncio
async def test_missing_credentials_are_unconfigured_and_secret_serialization_is_masked():
    item = ShioajiRealtimeProvider(None, None)
    capabilities = await item.get_capabilities()
    assert capabilities.license_status is LicenseStatus.UNCONFIGURED
    assert capabilities.configured is False
    assert await item.health() is False
    serialized = str(Settings(shioaji_api_key="key", shioaji_secret_key="secret").model_dump())
    assert "'key'" not in serialized and "'secret'" not in serialized


@pytest.mark.asyncio
async def test_manager_starts_normally_without_shioaji_credentials():
    item = ShioajiRealtimeProvider(None, None)
    manager = RealtimeProviderManager(
        item,
        SimpleNamespace(),
        SimpleNamespace(provider_status="UNKNOWN"),
    )
    await manager.start()
    assert manager._ingestion_task is None
    assert manager.hub.provider_status == "UNCONFIGURED"
    await manager.stop()


@pytest.mark.asyncio
async def test_contract_resolution_supports_twse_tpex_and_rejects_mismatch():
    item = make_provider()
    await item.connect()
    assert item.resolve_contract("TWSE:2330").exchange == "TSE"
    assert item.resolve_contract("TPEX:6488").exchange == "OTC"
    with pytest.raises(ShioajiProviderError, match="Unknown security"):
        item.resolve_contract("TWSE:9999")
    with pytest.raises(ShioajiProviderError, match="not TSE"):
        item.resolve_contract("TWSE:6488")


@pytest.mark.asyncio
async def test_shioaji_capabilities_publish_single_canonical_hard_limit():
    capabilities = await make_provider().get_capabilities()
    assert capabilities.subscription_hard_limit == 200


@pytest.mark.asyncio
async def test_callbacks_register_on_canonical_api_before_subscribe_and_stay_reachable():
    client = FakeClient()
    factory_calls = []

    def factory(_simulation):
        factory_calls.append(client)
        return client

    item = ShioajiRealtimeProvider("key", "secret", client_factory=factory)
    await item.connect()
    await item.acquire_subscription("owner", "TWSE:2330", RealtimeQuoteType.TICK)
    assert client.events[:4] == [
        "register:tick",
        "register:bidask",
        "register:event",
        "subscribe:tick",
    ]
    assert client.tick_callback is item._tick_callback
    assert client.bidask_callback is item._bidask_callback
    assert factory_calls == [client]


def test_tick_and_bidask_mapping_preserve_decimal_timestamp_and_depth():
    item = make_provider()
    quote = item.map_tick(
        "TSE",
        SimpleNamespace(
            code="2330",
            datetime=datetime(2026, 8, 21, 9, 1),
            close="123.450",
            volume=3,
            total_volume=103,
            sequence=7,
        ),
    )
    assert quote.market_id == "TWSE"
    assert quote.last_price == Decimal("123.450")
    assert quote.exchange_timestamp.tzinfo is UTC
    depth = item.map_bidask(
        "TSE",
        SimpleNamespace(
            code="2330",
            datetime=datetime(2026, 8, 21, 9, 1, 1),
            bid_price=["123.40", "123.35"],
            bid_volume=[4, 5],
            ask_price=["123.50", "123.55"],
            ask_volume=[6, 7],
        ),
    )
    assert depth.bid_prices == [Decimal("123.40"), Decimal("123.35")]
    assert depth.ask_volumes == [6, 7]


@pytest.mark.parametrize(
    ("exchange", "expected"),
    [
        (sj.Exchange.TSE, "TWSE"),
        (sj.Exchange.OTC, "TPEx"),
        ("TSE", "TWSE"),
        ("TWSE", "TWSE"),
        ("OTC", "TPEx"),
        ("TPEX", "TPEx"),
        ("Exchange.TSE", "TWSE"),
        ("Exchange.OTC", "TPEx"),
    ],
)
def test_stock_exchange_normalization(exchange, expected):
    assert ShioajiRealtimeProvider._market(exchange) == expected


def test_unknown_exchange_remains_explicit_error():
    with pytest.raises(ShioajiProviderError, match="Unsupported Shioaji exchange: TAIFEX"):
        ShioajiRealtimeProvider._market("TAIFEX")


@pytest.mark.asyncio
async def test_subscriptions_deduplicate_reference_count_and_restore():
    client = FakeClient()
    item = make_provider(client)
    await item.acquire("portfolio", "TWSE:2330", SubscriptionPriority.PORTFOLIO)
    await item.acquire("view", "TWSE:2330", SubscriptionPriority.VIEWED_SECURITY)
    await item.connect()
    assert sorted(client.quote.subscriptions) == [("2330", "bid_ask"), ("2330", "tick")]
    assert client.login_calls[0]["subscribe_trade"] is False
    await item.release("view", "TWSE:2330")
    assert client.quote.unsubscriptions == [("2330", "bid_ask")]
    assert ("TWSE:2330", RealtimeQuoteType.TICK) in item._registry.active
    await item.release("portfolio", "TWSE:2330")
    assert sorted(client.quote.unsubscriptions) == [("2330", "bid_ask"), ("2330", "tick")]


@pytest.mark.asyncio
async def test_disconnect_marks_stale_and_retains_requested_subscriptions():
    item = make_provider()
    await item.acquire("alert", "TWSE:2330", SubscriptionPriority.REALTIME_ALERT)
    await item.connect()
    item._loop = asyncio.get_running_loop()
    item.map_tick("TSE", SimpleNamespace(code="2330", close="10", volume=1, total_volume=1))
    item._on_event(0, -1, "", "disconnect")
    stale = await asyncio.wait_for(item._queue.get(), 0.1)
    assert stale.data_status is DataStatus.STALE
    assert ("TWSE:2330", "tick") in {(key, kind.value) for key, kind in item._registry.active}


@pytest.mark.asyncio
async def test_reconnect_restores_each_active_quote_type_once():
    client = FakeClient()
    item = make_provider(client)
    await item.acquire_subscription(
        "manager:tick", "TWSE:2330", RealtimeQuoteType.TICK
    )
    await item.acquire_subscription(
        "manager:bidask", "TWSE:2330", RealtimeQuoteType.BID_ASK
    )
    await item.connect()
    client.quote.subscriptions.clear()
    item._connected = False
    await item.connect()
    assert sorted(client.quote.subscriptions) == [("2330", "bid_ask"), ("2330", "tick")]
    assert client.events.count("register:tick") == 1
    assert client.events.count("register:bidask") == 1


@pytest.mark.asyncio
async def test_worker_thread_tick_callback_reaches_async_waiter():
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    event = SimpleNamespace(code="2330", close="101.5", volume=2, total_volume=20)
    worker = threading.Thread(target=client.tick_callback, args=(sj.Exchange.TSE, event))
    worker.start()
    result = await item.wait_for_event(RealtimeQuoteType.TICK, 0.5)
    worker.join()
    assert result.code == "2330"
    assert result.last_price == Decimal("101.5")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("quote_type", "callback_name", "event"),
    [
        (
            RealtimeQuoteType.TICK,
            "tick_callback",
            SimpleNamespace(code="2330", close="101.5", volume=2, total_volume=20),
        ),
        (
            RealtimeQuoteType.BID_ASK,
            "bidask_callback",
            SimpleNamespace(
                code="2330",
                bid_price=["101.0"],
                bid_volume=[2],
                ask_price=["101.5"],
                ask_volume=[3],
            ),
        ),
    ],
)
async def test_actual_registered_worker_callback_reaches_same_loop_waiter_with_diagnostics(
    quote_type, callback_name, event, caplog
):
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    running_loop = asyncio.get_running_loop()
    assert item._loop is running_loop
    assert item._loop.is_running() and not item._loop.is_closed()

    waiter = asyncio.create_task(item.wait_for_event(quote_type, 0.5))
    await asyncio.sleep(0)
    registered_callback = getattr(client, callback_name)
    expected_callback = (
        item._tick_callback
        if quote_type is RealtimeQuoteType.TICK
        else item._bidask_callback
    )
    assert registered_callback is expected_callback
    assert registered_callback.__self__ is item

    worker = threading.Thread(
        target=registered_callback, args=(sj.Exchange.TSE, event)
    )
    worker.start()
    result = await waiter
    worker.join()

    assert result.code == "2330"
    messages = [record.getMessage() for record in caplog.records]
    for stage in (
        "CALLBACK_NATIVE_ENTRY",
        "MAPPING_PASS",
        "CALLBACK_SCHEDULE_ATTEMPT",
        "CALLBACK_SCHEDULED",
        "CALLBACK_ASYNC_ENTRY",
        "OBSERVER_NOTIFY",
        "SMOKE_WAITER_RECEIVE",
    ):
        assert sum(f"stage={stage}" in message for message in messages) == 1
    assert all("loop_running=True loop_closed=False" in message for message in messages)


@pytest.mark.asyncio
async def test_registered_callback_surfaces_failure_before_mapping():
    class InvalidTick:
        @property
        def code(self):
            raise RuntimeError("unsafe payload detail")

    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    waiter = asyncio.create_task(item.wait_for_event(RealtimeQuoteType.TICK, 0.5))
    await asyncio.sleep(0)
    worker = threading.Thread(
        target=client.tick_callback, args=(sj.Exchange.TSE, InvalidTick())
    )
    worker.start()
    with pytest.raises(ShioajiCallbackError, match="tick callback mapping failed"):
        await waiter
    worker.join()
    assert item._last_error == "tick callback mapping failed: RuntimeError"


@pytest.mark.asyncio
async def test_scheduled_observer_failure_is_bounded(monkeypatch, caplog):
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    queue = item._smoke_queues[RealtimeQuoteType.TICK]

    def fail_delivery(_event):
        raise RuntimeError("unsafe payload detail")

    monkeypatch.setattr(queue, "put_nowait", fail_delivery)
    waiter = asyncio.create_task(item.wait_for_event(RealtimeQuoteType.TICK, 0.05))
    await asyncio.sleep(0)
    event = SimpleNamespace(code="2330", close="101.5", volume=2, total_volume=20)
    worker = threading.Thread(
        target=client.tick_callback, args=(sj.Exchange.TSE, event)
    )
    worker.start()
    with pytest.raises(TimeoutError):
        await waiter
    worker.join()
    assert item._last_error == "tick callback observer failed: RuntimeError"
    messages = [record.getMessage() for record in caplog.records]
    assert sum("stage=OBSERVER_NOTIFY_FAIL" in message for message in messages) == 1
    assert all("unsafe payload detail" not in message for message in messages)


@pytest.mark.asyncio
async def test_bidask_callback_maps_canonical_tse_exchange():
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    event = SimpleNamespace(
        code="2330",
        bid_price=["101.0"],
        bid_volume=[2],
        ask_price=["101.5"],
        ask_volume=[3],
    )
    worker = threading.Thread(target=client.bidask_callback, args=(sj.Exchange.TSE, event))
    worker.start()
    result = await item.wait_for_event(RealtimeQuoteType.BID_ASK, 0.5)
    worker.join()
    assert result.market_id == "TWSE"


@pytest.mark.asyncio
async def test_tick_callback_maps_canonical_otc_exchange():
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    event = SimpleNamespace(code="6488", close="88.8", volume=1, total_volume=5)
    worker = threading.Thread(target=client.tick_callback, args=(sj.Exchange.OTC, event))
    worker.start()
    result = await item.wait_for_event(RealtimeQuoteType.TICK, 0.5)
    worker.join()
    assert result.market_id == "TPEx"


@pytest.mark.asyncio
async def test_immediate_tick_and_bidask_callbacks_are_not_lost_after_subscribe():
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    client.quote.emit_on_subscribe = SimpleNamespace(
        code="2330", close="102", volume=1, total_volume=10
    )
    await item.acquire_subscription("tick", "TWSE:2330", RealtimeQuoteType.TICK)
    tick = await item.wait_for_event(RealtimeQuoteType.TICK, 0.1)
    assert tick.last_price == Decimal("102")

    client.quote.emit_on_subscribe = SimpleNamespace(
        code="2330",
        bid_price=["101.5"],
        bid_volume=[2],
        ask_price=["102.5"],
        ask_volume=[3],
    )
    await item.acquire_subscription("bidask", "TWSE:2330", RealtimeQuoteType.BID_ASK)
    bidask = await item.wait_for_event(RealtimeQuoteType.BID_ASK, 0.1)
    assert bidask.bid_prices == [Decimal("101.5")]


@pytest.mark.asyncio
async def test_worker_thread_mapping_error_reaches_waiter_as_bounded_failure():
    client = FakeClient()
    item = make_provider(client)
    await item.connect()
    invalid = SimpleNamespace(code="2330", close=None)
    worker = threading.Thread(target=client.tick_callback, args=("TSE", invalid))
    worker.start()
    with pytest.raises(ShioajiCallbackError, match="tick callback mapping failed"):
        await item.wait_for_event(RealtimeQuoteType.TICK, 0.5)
    worker.join()
    assert item._last_error == "tick callback mapping failed: ValidationError"


def test_bidask_domain_mapping_does_not_require_prior_tick():
    item = make_provider()
    event = item.map_bidask_event(
        "OTC",
        SimpleNamespace(
            code="6488",
            bid_price=["88.7"],
            bid_volume=[2],
            ask_price=["88.9"],
            ask_volume=[3],
        ),
    )
    assert event.market_id == "TPEx"
    assert event.bid_prices == [Decimal("88.7")]
    assert event.ask_volumes == [3]


@pytest.mark.asyncio
async def test_mapped_tick_enters_existing_cache_aggregation_and_alert_pipeline():
    item = make_provider()
    quote = item.map_tick("OTC", SimpleNamespace(code="6488", close="88.80", volume=2))
    cache = SimpleNamespace(save_and_publish_quote=AsyncMock(return_value=True))
    hub = SimpleNamespace(provider_status="UNCONFIGURED")
    aggregator = SimpleNamespace(accept=AsyncMock())
    alert = SimpleNamespace(accept=AsyncMock(), provider_status="UNCONFIGURED")
    manager = RealtimeProviderManager(
        item, cache, hub, aggregator=aggregator, alert_evaluator=alert
    )

    async def one_quote():
        yield quote
        manager._running = False

    item.stream_quotes = one_quote
    manager._running = True
    await manager._ingestion_loop()
    cache.save_and_publish_quote.assert_awaited_once_with(quote)
    aggregator.accept.assert_awaited_once_with(quote)
    alert.accept.assert_awaited_once_with(quote)
