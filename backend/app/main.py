from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.fake_realtime_provider import (
    FakeRealtimeProvider,
    UnconfiguredRealtimeProvider,
)
from app.adapters.shioaji_realtime_provider import ShioajiRealtimeProvider
from app.api.ai import router as ai_router
from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.comparison import router as comparison_router
from app.api.derivatives import router as derivatives_router
from app.api.exports import router as exports_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.industries import router as industries_router
from app.api.market import router as market_router
from app.api.portfolios import router as portfolios_router
from app.api.push import router as push_router
from app.api.realtime import router as realtime_router
from app.api.reports import router as reports_router
from app.api.screener import router as screener_router
from app.api.securities import router as securities_router
from app.api.sync import router as sync_router
from app.api.themes import router as themes_router
from app.api.watchlists import router as watchlists_router
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.repositories.realtime_membership import (
    RealtimeMembershipSnapshot,
    load_realtime_memberships,
)
from app.repositories.sql_alert import SqlAlertRepository
from app.services.intraday_candle_aggregator import IntradayCandleAggregator
from app.services.readiness import ReadinessChecker
from app.services.realtime_alerts import (
    RealtimeAlertEvaluationService,
    RealtimeAlertSubscriptionPolicy,
)
from app.services.realtime_cache import RealtimeCacheService
from app.services.realtime_hub import RealtimeQuoteHub
from app.services.realtime_provider_manager import RealtimeProviderManager
from app.services.realtime_strength import RealtimeTaxonomyAggregator

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.redis = redis
    app.state.readiness_checker = ReadinessChecker(engine, redis)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Realtime Quote Pipeline Initialization
    cache_service = RealtimeCacheService(redis)
    hub = RealtimeQuoteHub(redis, cache_service)
    aggregator = IntradayCandleAggregator(cache_service)
    try:
        async with app.state.session_factory() as membership_session:
            memberships = await load_realtime_memberships(membership_session)
    except Exception as error:
        logger.warning("realtime_membership_unavailable", error=str(error))
        memberships = RealtimeMembershipSnapshot()
    taxonomy_aggregator = RealtimeTaxonomyAggregator(memberships, cache_service)
    alert_session = app.state.session_factory()
    realtime_alert_service = RealtimeAlertEvaluationService(
        redis, SqlAlertRepository(alert_session)
    )
    try:
        await realtime_alert_service.refresh()
    except Exception as error:
        logger.warning("realtime_alerts_unavailable", error=str(error))
    if settings.realtime_provider.lower() == "shioaji":
        provider = ShioajiRealtimeProvider(
            settings.shioaji_api_key.get_secret_value() if settings.shioaji_api_key else None,
            settings.shioaji_secret_key.get_secret_value() if settings.shioaji_secret_key else None,
            settings.shioaji_simulation,
        )
    elif settings.app_env.lower() in {"development", "test", "ci"}:
        provider = FakeRealtimeProvider()
    else:
        provider = UnconfiguredRealtimeProvider()
    manager = RealtimeProviderManager(
        provider,
        cache_service,
        hub,
        aggregator,
        taxonomy_aggregator,
        realtime_alert_service,
        settings.realtime_broker_subscription_budget,
    )
    hub.subscription_manager = manager

    app.state.realtime_cache_service = cache_service
    app.state.realtime_hub = hub
    app.state.realtime_provider_manager = manager
    app.state.intraday_aggregator = aggregator
    app.state.realtime_taxonomy_aggregator = taxonomy_aggregator
    app.state.realtime_alert_service = realtime_alert_service

    await hub.start()
    await manager.start()
    alert_subscription_policy = None
    if settings.p1_alert_realtime_enabled:
        alert_subscription_policy = RealtimeAlertSubscriptionPolicy(
            realtime_alert_service, manager
        )
        await alert_subscription_policy.start()
    app.state.realtime_alert_subscription_policy = alert_subscription_policy

    yield

    if alert_subscription_policy is not None:
        await alert_subscription_policy.stop()
    await manager.stop()
    await hub.stop()
    await alert_session.close()
    await redis.aclose()
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health_router, prefix="/v1")
app.include_router(securities_router, prefix="/v1")
app.include_router(market_router, prefix="/v1")
app.include_router(derivatives_router, prefix="/v1")
app.include_router(portfolios_router, prefix="/v1")
app.include_router(watchlists_router, prefix="/v1")
app.include_router(alerts_router, prefix="/v1")
app.include_router(auth_router, prefix="/v1")
app.include_router(sync_router, prefix="/v1")
app.include_router(industries_router, prefix="/v1")
app.include_router(themes_router, prefix="/v1")
app.include_router(exports_router, prefix="/v1")
app.include_router(imports_router, prefix="/v1")
app.include_router(reports_router, prefix="/v1")
app.include_router(ai_router, prefix="/v1")
app.include_router(push_router, prefix="/v1")
app.include_router(screener_router)
app.include_router(comparison_router)
app.include_router(realtime_router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        request_id=request_id,
    )
    return response
