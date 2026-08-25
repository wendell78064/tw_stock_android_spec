import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from threading import Lock
from typing import Any
from zoneinfo import ZoneInfo

from app.adapters.realtime_base import RealtimeMarketDataProvider
from app.domain.realtime import (
    DataStatus,
    LicenseStatus,
    ProviderCapabilities,
    RealtimeBidAsk,
    RealtimeQuote,
    RealtimeQuoteType,
    TradingSession,
)

TAIPEI = ZoneInfo("Asia/Taipei")
logger = logging.getLogger(__name__)


class ShioajiProviderError(RuntimeError):
    pass


class ShioajiCallbackError(ShioajiProviderError):
    pass


class SubscriptionPriority(StrEnum):
    PORTFOLIO = "P0"
    REALTIME_ALERT = "P1"
    VIEWED_SECURITY = "P2"
    INDUSTRY_REPRESENTATIVE = "P3"
    WATCHLIST = "P4"


QuoteKind = RealtimeQuoteType


class SubscriptionRegistry:
    """Owner-aware desired state; the provider applies only effective deltas."""

    def __init__(self) -> None:
        self._owners: dict[tuple[str, QuoteKind], set[str]] = defaultdict(set)

    def acquire(self, owner: str, key: str, kinds: set[QuoteKind]) -> set[QuoteKind]:
        added = set()
        for kind in kinds:
            identity = (key.upper(), kind)
            if not self._owners[identity]:
                added.add(kind)
            self._owners[identity].add(owner)
        return added

    def release(self, owner: str, key: str) -> set[QuoteKind]:
        removed = set()
        for identity in [item for item in self._owners if item[0] == key.upper()]:
            owners = self._owners[identity]
            owners.discard(owner)
            if not owners:
                removed.add(identity[1])
                del self._owners[identity]
        return removed

    @property
    def active(self) -> set[tuple[str, QuoteKind]]:
        return set(self._owners)


class ShioajiRealtimeProvider(RealtimeMarketDataProvider):
    provider_name = "SINOPAC_SHIOAJI"
    _exchange_by_market = {"TWSE": "TSE", "TPEX": "OTC"}

    def __init__(
        self,
        api_key: str | None,
        secret_key: str | None,
        simulation: bool = False,
        client_factory: Callable[[bool], Any] | None = None,
        reconnect_delays: tuple[float, ...] = (1.0, 2.0, 5.0, 10.0, 30.0),
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._simulation = simulation
        self._client_factory = client_factory or self._official_client
        self._reconnect_delays = reconnect_delays
        self._client: Any = None
        self._queue: asyncio.Queue[RealtimeQuote] = asyncio.Queue()
        self._smoke_queues: dict[RealtimeQuoteType, asyncio.Queue[Any]] = {
            kind: asyncio.Queue(maxsize=1) for kind in RealtimeQuoteType
        }
        self._registry = SubscriptionRegistry()
        self._connected = False
        self._closing = False
        self._last_error: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._latest: dict[str, RealtimeQuote] = {}
        self._sequence = 0
        self._callbacks_installed_client: Any = None
        self._tick_callback = self._on_tick
        self._bidask_callback = self._on_bidask
        self._event_callback = self._on_event
        self._smoke_waiters: set[RealtimeQuoteType] = set()
        self._diagnostic_stages: dict[RealtimeQuoteType, set[str]] = {
            kind: set() for kind in RealtimeQuoteType
        }
        self._diagnostic_lock = Lock()

    @staticmethod
    def _official_client(simulation: bool) -> Any:
        import shioaji as sj

        return sj.Shioaji(simulation=simulation)

    @property
    def configured(self) -> bool:
        return bool(self._api_key and self._secret_key)

    async def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider_name=self.provider_name,
            source_type="WEBSOCKET",
            realtime_available=self._connected,
            redistribution_allowed=False,
            license_status=(
                LicenseStatus.AUTHORIZED if self.configured else LicenseStatus.UNCONFIGURED
            ),
            configured=self.configured,
            last_error=self._last_error,
        )

    async def connect(self) -> None:
        if not self.configured:
            return
        self._loop = asyncio.get_running_loop()
        try:
            if self._client is None:
                self._client = self._client_factory(self._simulation)
            await asyncio.to_thread(
                self._client.login,
                api_key=self._api_key,
                secret_key=self._secret_key,
                subscribe_trade=False,
            )
            self._install_callbacks()
            self._connected = True
            self._last_error = None
            await self._restore_subscriptions()
        except Exception as error:
            self._connected = False
            self._last_error = str(error)
            raise ShioajiProviderError("Shioaji connection failed") from error

    def _install_callbacks(self) -> None:
        if self._callbacks_installed_client is self._client:
            return
        self._client.set_on_tick_stk_v1_callback(self._tick_callback)
        self._client.set_on_bidask_stk_v1_callback(self._bidask_callback)
        if hasattr(self._client, "set_event_callback"):
            self._client.set_event_callback(self._event_callback)
        self._callbacks_installed_client = self._client

    def resolve_contract(self, security_key: str) -> Any:
        try:
            market, code = security_key.upper().split(":", 1)
        except ValueError as error:
            raise ShioajiProviderError(f"Invalid security key: {security_key}") from error
        expected = self._exchange_by_market.get(market)
        if expected is None:
            raise ShioajiProviderError(f"Unsupported market: {market}")
        contract = self._client.contracts.get(code)
        if contract is None:
            raise ShioajiProviderError(f"Unknown security: {market}:{code}")
        exchange = str(getattr(contract, "exchange", "")).upper()
        if exchange != expected:
            raise ShioajiProviderError(
                f"Security {code} belongs to {exchange or 'UNKNOWN'}, not {expected}"
            )
        return contract

    async def acquire(
        self,
        owner: str,
        security_key: str,
        priority: SubscriptionPriority,
    ) -> None:
        kinds = (
            {QuoteKind.TICK, QuoteKind.BID_ASK}
            if priority is SubscriptionPriority.VIEWED_SECURITY
            else {QuoteKind.TICK}
        )
        added = self._registry.acquire(owner, security_key, kinds)
        if self._connected:
            await self._apply(security_key, added, subscribe=True)

    async def acquire_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        added = self._registry.acquire(owner, security_key, {quote_type})
        if self._connected:
            await self._apply(security_key, added, subscribe=True)

    async def release_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        identity = (security_key.upper(), quote_type)
        owners = self._registry._owners.get(identity)
        if not owners or owner not in owners:
            return
        owners.remove(owner)
        if owners:
            return
        del self._registry._owners[identity]
        if self._connected:
            await self._apply(security_key, {quote_type}, subscribe=False)

    async def release(self, owner: str, security_key: str) -> None:
        removed = self._registry.release(owner, security_key)
        if self._connected:
            await self._apply(security_key, removed, subscribe=False)

    async def subscribe_quotes(self, security_keys: list[str]) -> None:
        for key in security_keys:
            await self.acquire("legacy", key, SubscriptionPriority.VIEWED_SECURITY)

    async def unsubscribe_quotes(self, security_keys: list[str]) -> None:
        for key in security_keys:
            await self.release("legacy", key)

    async def _apply(self, key: str, kinds: set[QuoteKind], subscribe: bool) -> None:
        if not kinds:
            return
        contract = self.resolve_contract(key)
        method = self._client.quote.subscribe if subscribe else self._client.quote.unsubscribe
        for kind in sorted(kinds):
            await asyncio.to_thread(method, contract, quote_type=kind.value)

    async def _restore_subscriptions(self) -> None:
        for key, kind in sorted(self._registry.active):
            await self._apply(key, {kind}, subscribe=True)

    async def stream_quotes(self) -> AsyncGenerator[RealtimeQuote, None]:
        attempt = 0
        while not self._closing:
            if not self.configured:
                return
            if not self._connected:
                try:
                    await self.connect()
                    attempt = 0
                except ShioajiProviderError:
                    delay = self._reconnect_delays[min(attempt, len(self._reconnect_delays) - 1)]
                    attempt += 1
                    await asyncio.sleep(delay)
                    continue
            try:
                quote = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError as error:
                if not self._connected:
                    raise ShioajiProviderError("Shioaji disconnected") from error
                continue
            yield quote

    def _on_event(self, _response_code: int, event_code: int, _info: str, _event: str) -> None:
        if event_code < 0:
            self._connected = False
            self._last_error = f"Shioaji quote event {event_code}"
            for quote in self._latest.values():
                self._enqueue(quote.model_copy(update={"data_status": DataStatus.STALE}))

    @staticmethod
    def _value(event: Any, name: str, default: Any = None) -> Any:
        return getattr(event, name, default)

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        return None if value is None else Decimal(str(value))

    @classmethod
    def _timestamp(cls, event: Any) -> datetime:
        value = cls._value(event, "datetime") or cls._value(event, "timestamp")
        if isinstance(value, datetime):
            moment = value
        elif isinstance(value, int | float):
            divisor = 1_000_000_000 if value > 10**17 else 1_000_000 if value > 10**14 else 1
            moment = datetime.fromtimestamp(value / divisor, tz=UTC)
        elif isinstance(value, str):
            moment = datetime.fromisoformat(value)
        else:
            moment = datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=TAIPEI)
        return moment.astimezone(UTC)

    @classmethod
    def _market(cls, exchange: Any) -> str:
        canonical = getattr(exchange, "value", None)
        if canonical is None:
            canonical = getattr(exchange, "name", None)
        raw = str(canonical if canonical is not None else exchange).strip().upper()
        if raw.startswith("EXCHANGE."):
            raw = raw.removeprefix("EXCHANGE.")
        if raw in {"TSE", "TWSE"}:
            return "TWSE"
        if raw in {"OTC", "TPEX"}:
            return "TPEx"
        raise ShioajiProviderError(f"Unsupported Shioaji exchange: {raw}")

    def map_tick(self, exchange: Any, event: Any) -> RealtimeQuote:
        market = self._market(exchange)
        code = str(self._value(event, "code"))
        now = datetime.now(UTC)
        self._sequence += 1
        quote = RealtimeQuote(
            security_id=f"sec_{code}",
            market_id=market,
            code=code,
            exchange_timestamp=self._timestamp(event),
            received_at=now,
            last_price=self._decimal(self._value(event, "close")),
            last_size=int(self._value(event, "volume", 0) or 0),
            open_price=self._decimal(self._value(event, "open")),
            high_price=self._decimal(self._value(event, "high")),
            low_price=self._decimal(self._value(event, "low")),
            total_volume=int(self._value(event, "total_volume", 0) or 0),
            sequence=int(self._value(event, "sequence", self._sequence) or self._sequence),
            data_status=DataStatus.LIVE,
            provider=self.provider_name,
            source_timestamp=self._timestamp(event),
            session=TradingSession.REGULAR,
        )
        self._latest[quote.composite_key] = quote
        return quote

    def map_bidask(self, exchange: Any, event: Any) -> RealtimeQuote | None:
        mapped = self.map_bidask_event(exchange, event)
        return self._enrich_quote_with_bidask(mapped)

    def _enrich_quote_with_bidask(self, mapped: RealtimeBidAsk) -> RealtimeQuote | None:
        key = f"{mapped.market_id.upper()}:{mapped.code}"
        previous = self._latest.get(key)
        if previous is None:
            return None
        quote = previous.model_copy(
            update={
                "exchange_timestamp": mapped.exchange_timestamp,
                "received_at": mapped.received_at,
                "bid_price": mapped.bid_prices[0] if mapped.bid_prices else None,
                "bid_size": mapped.bid_volumes[0] if mapped.bid_volumes else None,
                "ask_price": mapped.ask_prices[0] if mapped.ask_prices else None,
                "ask_size": mapped.ask_volumes[0] if mapped.ask_volumes else None,
                "bid_prices": mapped.bid_prices,
                "bid_volumes": mapped.bid_volumes,
                "ask_prices": mapped.ask_prices,
                "ask_volumes": mapped.ask_volumes,
            }
        )
        self._latest[key] = quote
        return quote

    def map_bidask_event(self, exchange: Any, event: Any) -> RealtimeBidAsk:
        market = self._market(exchange)
        code = str(self._value(event, "code"))
        bid_prices = [Decimal(str(value)) for value in self._value(event, "bid_price", [])]
        ask_prices = [Decimal(str(value)) for value in self._value(event, "ask_price", [])]
        return RealtimeBidAsk(
            market_id=market,
            code=code,
            exchange_timestamp=self._timestamp(event),
            received_at=datetime.now(UTC),
            bid_prices=bid_prices,
            bid_volumes=list(self._value(event, "bid_volume", [])),
            ask_prices=ask_prices,
            ask_volumes=list(self._value(event, "ask_volume", [])),
            provider=self.provider_name,
        )

    def _enqueue(self, quote: RealtimeQuote | None) -> None:
        if quote is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, quote)

    def _on_tick(self, exchange: Any, event: Any) -> None:
        self._diagnostic_stage(
            RealtimeQuoteType.TICK, "CALLBACK_NATIVE_ENTRY", exchange, event
        )
        market = "UNKNOWN"
        code = "UNKNOWN"
        try:
            market = str(exchange)
            code = str(self._value(event, "code", "UNKNOWN"))
            quote = self.map_tick(exchange, event)
            self._diagnostic_stage(
                RealtimeQuoteType.TICK, "MAPPING_PASS", exchange, event
            )
            logger.debug(
                "shioaji_callback event=tick market=%s code=%s entered=yes mapping_success=yes",
                market,
                code,
            )
            self._enqueue_smoke(RealtimeQuoteType.TICK, quote)
            self._enqueue(quote)
        except Exception as error:
            self._record_callback_error(RealtimeQuoteType.TICK, market, code, error)

    def _on_bidask(self, exchange: Any, event: Any) -> None:
        self._diagnostic_stage(
            RealtimeQuoteType.BID_ASK, "CALLBACK_NATIVE_ENTRY", exchange, event
        )
        market = "UNKNOWN"
        code = "UNKNOWN"
        try:
            market = str(exchange)
            code = str(self._value(event, "code", "UNKNOWN"))
            mapped = self.map_bidask_event(exchange, event)
            self._diagnostic_stage(
                RealtimeQuoteType.BID_ASK, "MAPPING_PASS", exchange, event
            )
            logger.debug(
                "shioaji_callback event=bidask market=%s code=%s entered=yes mapping_success=yes",
                market,
                code,
            )
            self._enqueue_smoke(RealtimeQuoteType.BID_ASK, mapped)
            self._enqueue(self._enrich_quote_with_bidask(mapped))
        except Exception as error:
            self._record_callback_error(RealtimeQuoteType.BID_ASK, market, code, error)

    def _record_callback_error(
        self,
        quote_type: RealtimeQuoteType,
        market: str,
        code: str,
        error: Exception,
    ) -> None:
        self._last_error = f"{quote_type.value} callback mapping failed: {type(error).__name__}"
        self._diagnostic_stage(quote_type, "MAPPING_FAIL", market, event=None, code=code)
        logger.warning(
            "shioaji_callback event=%s market=%s code=%s entered=yes mapping_success=no",
            quote_type.value,
            market,
            code,
        )
        self._enqueue_smoke(
            quote_type,
            ShioajiCallbackError(f"{quote_type.value} callback mapping failed"),
        )

    def _diagnostic_stage(
        self,
        quote_type: RealtimeQuoteType,
        stage: str,
        exchange: Any = None,
        event: Any = None,
        *,
        code: Any = None,
    ) -> None:
        """Emit each smoke-only callback stage at most once without payload data."""
        try:
            with self._diagnostic_lock:
                if quote_type not in self._smoke_waiters:
                    return
                stages = self._diagnostic_stages[quote_type]
                if stage in stages:
                    return
                stages.add(stage)
            loop = self._loop
            try:
                market = str(exchange) if exchange is not None else "UNKNOWN"
            except Exception:
                market = "UNKNOWN"
            if code is None:
                try:
                    code = self._value(event, "code", "UNKNOWN")
                except Exception:
                    code = "UNKNOWN"
            logger.warning(
                "shioaji_callback_diag event=%s stage=%s market=%s code=%s "
                "loop_running=%s loop_closed=%s",
                quote_type.value,
                stage,
                market,
                str(code),
                bool(loop and loop.is_running()),
                bool(loop and loop.is_closed()),
            )
        except Exception:
            # Diagnostics must never interfere with market-data delivery.
            return

    def _enqueue_smoke(self, quote_type: RealtimeQuoteType, event: Any) -> None:
        self._diagnostic_stage(quote_type, "CALLBACK_SCHEDULE_ATTEMPT", event=event)
        loop = self._loop
        if loop is None:
            return
        queue = self._smoke_queues[quote_type]

        def put() -> None:
            self._diagnostic_stage(quote_type, "CALLBACK_ASYNC_ENTRY", event=event)
            try:
                if queue.empty():
                    queue.put_nowait(event)
                    self._diagnostic_stage(quote_type, "OBSERVER_NOTIFY", event=event)
            except Exception as error:
                self._last_error = (
                    f"{quote_type.value} callback observer failed: {type(error).__name__}"
                )
                self._diagnostic_stage(quote_type, "OBSERVER_NOTIFY_FAIL", event=event)

        try:
            loop.call_soon_threadsafe(put)
            self._diagnostic_stage(quote_type, "CALLBACK_SCHEDULED", event=event)
        except Exception as error:
            self._last_error = (
                f"{quote_type.value} callback scheduling failed: {type(error).__name__}"
            )
            self._diagnostic_stage(quote_type, "CALLBACK_SCHEDULE_FAIL", event=event)

    async def wait_for_event(self, quote_type: RealtimeQuoteType, timeout: float) -> Any:
        with self._diagnostic_lock:
            self._diagnostic_stages[quote_type].clear()
            self._smoke_waiters.add(quote_type)
        try:
            result = await asyncio.wait_for(
                self._smoke_queues[quote_type].get(), timeout=timeout
            )
            self._diagnostic_stage(
                quote_type, "SMOKE_WAITER_RECEIVE", event=result
            )
            if isinstance(result, BaseException):
                raise result
            return result
        finally:
            with self._diagnostic_lock:
                self._smoke_waiters.discard(quote_type)

    async def health(self) -> bool:
        return self._connected

    async def close(self) -> None:
        self._closing = True
        self._connected = False
        if self._client is not None and hasattr(self._client, "logout"):
            await asyncio.to_thread(self._client.logout)
