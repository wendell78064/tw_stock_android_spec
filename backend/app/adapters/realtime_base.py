from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from app.domain.realtime import ProviderCapabilities, RealtimeQuote


class RealtimeMarketDataProvider(ABC):
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
