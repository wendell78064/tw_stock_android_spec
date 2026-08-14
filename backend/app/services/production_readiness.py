from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.realtime import LicenseStatus, ProviderCapabilities
from app.services.ai_grounding import AIAnalysisProvider
from app.services.push_notifications import PushNotificationProvider


class RealtimeProductionGate:
    """Evaluates whether a realtime provider meets all production criteria to serve LIVE data."""

    @staticmethod
    def evaluate(capabilities: ProviderCapabilities | None) -> dict[str, Any]:
        if not capabilities or not capabilities.configured:
            return {
                "status": "UNCONFIGURED",
                "can_serve_live": False,
                "reason": "Realtime provider is not configured",
            }

        if not capabilities.realtime_available:
            return {
                "status": "DELAYED" if capabilities.delay_seconds > 0 else "UNAVAILABLE",
                "can_serve_live": False,
                "delay_seconds": capabilities.delay_seconds,
                "reason": "Realtime quotes not available on this provider tier",
            }

        if capabilities.license_status != LicenseStatus.AUTHORIZED:
            return {
                "status": "UNAUTHORIZED",
                "can_serve_live": False,
                "reason": f"License status is {capabilities.license_status.value}",
            }

        if not capabilities.redistribution_allowed:
            return {
                "status": "UNAUTHORIZED_REDISTRIBUTION",
                "can_serve_live": False,
                "reason": "Redistribution is not authorized under current vendor agreement",
            }

        return {
            "status": "LIVE",
            "can_serve_live": True,
            "source_type": capabilities.source_type.value,
        }


class ProductionReadinessService:
    def __init__(
        self,
        session: AsyncSession,
        ai_provider: AIAnalysisProvider,
        push_provider: PushNotificationProvider,
        realtime_capabilities: ProviderCapabilities | None = None,
        redis_client: Any = None,
    ):
        self.session = session
        self.ai_provider = ai_provider
        self.push_provider = push_provider
        self.realtime_caps = realtime_capabilities
        self.redis = redis_client

    async def check_health(self) -> dict[str, Any]:
        db_ok = False
        try:
            res = await self.session.execute(text("SELECT 1"))
            db_ok = res.scalar() == 1
        except Exception:
            db_ok = False

        redis_ok = False
        if self.redis:
            try:
                redis_ok = await self.redis.ping()
            except Exception:
                redis_ok = False

        ai_health = await self.ai_provider.health()
        push_health = await self.push_provider.health()
        realtime_gate = RealtimeProductionGate.evaluate(self.realtime_caps)

        is_healthy = db_ok
        is_ready = db_ok

        return {
            "status": "HEALTHY" if is_healthy else "UNHEALTHY",
            "ready": is_ready,
            "components": {
                "database": {"status": "UP" if db_ok else "DOWN"},
                "redis": {"status": "UP" if redis_ok else "UNAVAILABLE"},
                "ai_provider": ai_health,
                "push_provider": push_health,
                "realtime_provider": realtime_gate,
            },
        }
