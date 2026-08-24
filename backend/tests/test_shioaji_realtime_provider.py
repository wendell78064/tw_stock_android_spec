import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.adapters.shioaji_realtime_provider import (
    ShioajiProviderError,
    ShioajiRealtimeProvider,
    SubscriptionPriority,
)
from app.core.settings import Settings
from app.domain.realtime import DataStatus, LicenseStatus, RealtimeQuoteType
from app.services.realtime_provider_manager import RealtimeProviderManager


class FakeQuoteClient:
    def __init__(self):
        self.subscriptions = []
        self.unsubscriptions = []

    def set_on_tick_stk_v1_callback(self, callback):
        self.tick_callback = callback

    def set_on_bidask_stk_v1_callback(self, callback):
        self.bidask_callback = callback

    def set_event_callback(self, callback):
        self.event_callback = callback

    def subscribe(self, contract, quote_type):
        self.subscriptions.append((contract.code, quote_type))

    def unsubscribe(self, contract, quote_type):
        self.unsubscriptions.append((contract.code, quote_type))


class FakeClient:
    def __init__(self):
        self.quote = FakeQuoteClient()
        self.contracts = SimpleNamespace(
            get=lambda code: {
                "2330": SimpleNamespace(code="2330", exchange="TSE"),
                "6488": SimpleNamespace(code="6488", exchange="OTC"),
            }.get(code)
        )
        self.login_calls = []

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
    assert client.quote.unsubscriptions == []
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
