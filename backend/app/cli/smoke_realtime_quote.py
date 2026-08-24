import argparse
import asyncio
import re
from typing import Any

from app.adapters.shioaji_realtime_provider import (
    ShioajiProviderError,
    ShioajiRealtimeProvider,
)
from app.core.settings import get_settings
from app.domain.realtime import RealtimeBidAsk, RealtimeQuote, RealtimeQuoteType

CODE_PATTERN = re.compile(r"^[0-9]{4,6}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bounded Shioaji market-data smoke")
    parser.add_argument("--market", required=True, choices=("TWSE", "TPEX"))
    parser.add_argument("--code", required=True)
    parser.add_argument("--quote-type", required=True, choices=("tick", "bidask"))
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    if not CODE_PATTERN.fullmatch(args.code):
        parser.error("code must contain 4 to 6 digits")
    if not 0 < args.timeout <= 30:
        parser.error("timeout must be between 0 and 30 seconds")
    return args


def _validate_event(event: Any, quote_type: RealtimeQuoteType, market: str, code: str) -> None:
    if event.market_id.upper() != market or event.code != code:
        raise ShioajiProviderError("Unexpected security event")
    if event.exchange_timestamp.tzinfo is None or event.received_at.tzinfo is None:
        raise ShioajiProviderError("Realtime timestamp is not timezone-aware")
    if quote_type is RealtimeQuoteType.TICK:
        if not isinstance(event, RealtimeQuote) or event.last_price is None:
            raise ShioajiProviderError("Invalid Tick mapping")
    elif not isinstance(event, RealtimeBidAsk) or not (
        event.bid_prices or event.ask_prices
    ):
        raise ShioajiProviderError("Invalid BidAsk mapping")


async def smoke(
    provider: ShioajiRealtimeProvider,
    market: str,
    code: str,
    quote_type: RealtimeQuoteType,
    timeout: float,
) -> None:
    key = f"{market}:{code}"
    owner = "production-smoke"
    subscribed = False
    waiter: asyncio.Task[Any] | None = None
    try:
        await provider.connect()
        print("LOGIN=PASS")
        provider.resolve_contract(key)
        print("CONTRACT=PASS")
        waiter = asyncio.create_task(provider.wait_for_event(quote_type, timeout))
        await asyncio.sleep(0)
        await provider.acquire_subscription(owner, key, quote_type)
        subscribed = True
        print("SUBSCRIBE=PASS")
        event = await waiter
        _validate_event(event, quote_type, market, code)
        print("EVENT=PASS")
    finally:
        if waiter is not None and not waiter.done():
            waiter.cancel()
        if subscribed:
            await provider.release_subscription(owner, key, quote_type)
            print("UNSUBSCRIBE=PASS")
        await provider.close()


async def async_main() -> int:
    args = parse_args()
    settings = get_settings()
    if settings.realtime_provider.lower() != "shioaji":
        print("ERROR=ENVIRONMENT")
        return 2
    api_key = settings.shioaji_api_key.get_secret_value() if settings.shioaji_api_key else None
    secret_key = (
        settings.shioaji_secret_key.get_secret_value() if settings.shioaji_secret_key else None
    )
    if not api_key or not secret_key:
        print("ERROR=ENVIRONMENT")
        return 2
    provider = ShioajiRealtimeProvider(api_key, secret_key, settings.shioaji_simulation)
    quote_type = (
        RealtimeQuoteType.TICK
        if args.quote_type == "tick"
        else RealtimeQuoteType.BID_ASK
    )
    try:
        await smoke(provider, args.market, args.code, quote_type, args.timeout)
    except TimeoutError:
        print("ERROR=TIMEOUT")
        return 3
    except ShioajiProviderError:
        print("ERROR=PROVIDER")
        return 4
    except Exception:
        print("ERROR=RUNTIME")
        return 5
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
