from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.alerts import router as alerts_router
from app.api.derivatives import router as derivatives_router
from app.api.health import router as health_router
from app.api.industries import router as industries_router
from app.api.market import router as market_router
from app.api.portfolios import router as portfolios_router
from app.api.securities import router as securities_router
from app.api.themes import router as themes_router
from app.api.watchlists import router as watchlists_router
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.services.readiness import ReadinessChecker

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
    yield
    await redis.aclose()
    await engine.dispose()


from app.api.screener import router as screener_router

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(health_router, prefix="/v1")
app.include_router(securities_router, prefix="/v1")
app.include_router(market_router, prefix="/v1")
app.include_router(derivatives_router, prefix="/v1")
app.include_router(portfolios_router, prefix="/v1")
app.include_router(watchlists_router, prefix="/v1")
app.include_router(alerts_router, prefix="/v1")
app.include_router(industries_router, prefix="/v1")
app.include_router(themes_router, prefix="/v1")
app.include_router(screener_router)



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
