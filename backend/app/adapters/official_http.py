import asyncio
from collections.abc import Callable
from typing import Any

import httpx


class UpstreamSchemaError(ValueError):
    pass


class OfficialJsonClient:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout: float = 20,
        attempts: int = 3,
        min_interval: float = 0.15,
        sleep: Callable = asyncio.sleep,
    ):
        self.client = client
        self.timeout = timeout
        self.attempts = attempts
        self.min_interval = min_interval
        self.sleep = sleep
        self._lock = asyncio.Lock()

    async def get_list(self, url: str, required: set[str]) -> list[dict[str, Any]]:
        owned = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "TWMarketLedger/0.2 (+official-eod-adapter)"},
            follow_redirects=True,
        )
        try:
            for attempt in range(self.attempts):
                try:
                    async with self._lock:
                        response = await client.get(url, headers={"Accept": "application/json"})
                        await self.sleep(self.min_interval)
                    if response.status_code == 429 or response.status_code >= 500:
                        response.raise_for_status()
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, list):
                        raise UpstreamSchemaError("official response must be a JSON array")
                    if payload and not required.issubset(payload[0]):
                        missing = sorted(required - payload[0].keys())
                        raise UpstreamSchemaError(f"official response missing fields: {missing}")
                    return payload
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                    if attempt + 1 == self.attempts:
                        raise
                    await self.sleep(0.25 * 2**attempt)
            return []
        finally:
            if owned:
                await client.aclose()

    async def get_object(self, url: str, required: set[str]) -> dict[str, Any]:
        owned = self.client is None
        client = self.client or httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "TWMarketLedger/0.2 (+official-eod-adapter)"},
            follow_redirects=True,
        )
        try:
            for attempt in range(self.attempts):
                try:
                    async with self._lock:
                        response = await client.get(url, headers={"Accept": "application/json"})
                        await self.sleep(self.min_interval)
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict) or not required.issubset(payload):
                        raise UpstreamSchemaError("official response object schema mismatch")
                    return payload
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                    if attempt + 1 == self.attempts:
                        raise
                    await self.sleep(0.25 * 2**attempt)
            return {}
        finally:
            if owned:
                await client.aclose()
