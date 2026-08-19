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
                    if not response.content or not response.text.strip():
                        return []
                    try:
                        payload = response.json()
                    except Exception as error:
                        content_type = response.headers.get("content-type", "unknown")
                        raise UpstreamSchemaError(
                            f"official response at {url} (status={response.status_code}, content_type={content_type}) failed JSON decoding: {error}"
                        ) from error
                    if not isinstance(payload, list):
                        raise UpstreamSchemaError(
                            f"official response at {url} (status={response.status_code}) must be a JSON array"
                        )
                    if payload and not required.issubset(payload[0]):
                        missing = sorted(required - payload[0].keys())
                        raise UpstreamSchemaError(
                            f"official response at {url} missing fields: {missing}"
                        )
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
                    if response.status_code == 429 or response.status_code >= 500:
                        response.raise_for_status()
                    response.raise_for_status()
                    if not response.content or not response.text.strip():
                        return {}
                    try:
                        payload = response.json()
                    except Exception as error:
                        content_type = response.headers.get("content-type", "unknown")
                        raise UpstreamSchemaError(
                            f"official response at {url} (status={response.status_code}, content_type={content_type}) failed JSON decoding: {error}"
                        ) from error
                    if not isinstance(payload, dict) or not required.issubset(payload):
                        missing = sorted(required - set(payload.keys())) if isinstance(payload, dict) else "not an object"
                        raise UpstreamSchemaError(
                            f"official response at {url} (status={response.status_code}) object schema mismatch, missing: {missing}"
                        )
                    return payload
                except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError):
                    if attempt + 1 == self.attempts:
                        raise
                    await self.sleep(0.25 * 2**attempt)
            return {}
        finally:
            if owned:
                await client.aclose()
