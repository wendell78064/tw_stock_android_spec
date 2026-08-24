from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.domain.realtime import ProviderCapabilities, RealtimeQuote, RealtimeQuoteType


class RealtimeMarketDataProvider(ABC):
    async def acquire_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        """Acquire one broker resource; manager provides global reference counting."""
        await self.subscribe_quotes([security_key])

    async def release_subscription(
        self, owner: str, security_key: str, quote_type: RealtimeQuoteType
    ) -> None:
        """Release one broker resource after the last manager consumer leaves."""
        await self.unsubscribe_quotes([security_key])

    @abstractmethod
    async def get_capabilities(self) -> ProviderCapabilities:
        """Return legal boundaries and capabilities of this provider."""
        pass

    @abstractmethod
    async def subscribe_quotes(self, security_keys: list[str]) -> None:
        """Subscribe to real-time quotes for given 'MARKET:CODE' keys."""
        pass

    @abstractmethod
    async def unsubscribe_quotes(self, security_keys: list[str]) -> None:
        """Unsubscribe from real-time quotes for given 'MARKET:CODE' keys."""
        pass

    @abstractmethod
    async def stream_quotes(self) -> AsyncGenerator[RealtimeQuote, None]:
        """Yield normalized RealtimeQuote events."""
        pass

    @abstractmethod
    async def health(self) -> bool:
        """Return provider connection health state."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up provider resources and connections."""
        pass
