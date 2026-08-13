from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.settings import Settings, get_settings
from app.repositories.sql_alert import SqlAlertRepository
from app.repositories.sql_derivatives import SqlDerivativesRepository
from app.repositories.sql_industry import SqlIndustryRepository
from app.repositories.sql_industry_strength import SqlIndustryStrengthRepository
from app.repositories.sql_market_spot import SqlMarketSpotRepository
from app.repositories.sql_portfolio import SqlPortfolioRepository
from app.repositories.sql_price import SqlPriceRepository
from app.repositories.sql_screener import SqlScreenerRepository
from app.repositories.sql_security import SqlSecurityRepository
from app.repositories.sql_watchlist import SqlWatchlistRepository
from app.services.auth import AuthService
from app.services.cloud_sync import CloudSyncService
from app.services.comparison import ComparisonService
from app.services.readiness import ReadinessChecker
from app.services.screener_query import ScreenerQueryService

bearer = HTTPBearer(auto_error=False)


def readiness_checker(request: Request) -> ReadinessChecker:
    return request.app.state.readiness_checker


def redis_client(request: Request) -> Redis:
    return request.app.state.redis


def get_realtime_cache_service(request: Request):
    return request.app.state.realtime_cache_service


def get_realtime_hub(request: Request):
    return request.app.state.realtime_hub


def get_realtime_provider_manager(request: Request):
    return request.app.state.realtime_provider_manager


def get_intraday_aggregator(request: Request):
    return request.app.state.intraday_aggregator


def get_realtime_alert_service(request: Request):
    return request.app.state.realtime_alert_service


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def auth_service(
    session: Annotated[AsyncSession, Depends(database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        session,
        settings.effective_auth_secret(),
        settings.access_token_minutes,
        settings.refresh_token_days,
    )


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[AuthService, Depends(auth_service)],
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("UNAUTHENTICATED", "bearer token is required", 401)
    return await service.authenticate(credentials.credentials)


async def cloud_sync_service(
    session: Annotated[AsyncSession, Depends(database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CloudSyncService:
    return CloudSyncService(session, settings.sync_page_limit)


async def comparison_service(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> ComparisonService:
    return ComparisonService(session)


async def security_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlSecurityRepository:
    return SqlSecurityRepository(session)


async def price_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlPriceRepository:
    return SqlPriceRepository(session)


async def market_spot_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlMarketSpotRepository:
    return SqlMarketSpotRepository(session)


async def derivatives_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlDerivativesRepository:
    return SqlDerivativesRepository(session)


async def portfolio_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlPortfolioRepository:
    return SqlPortfolioRepository(session)


async def watchlist_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlWatchlistRepository:
    return SqlWatchlistRepository(session)


async def alert_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlAlertRepository:
    return SqlAlertRepository(session)


async def industry_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlIndustryRepository:
    return SqlIndustryRepository(session)


async def industry_strength_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlIndustryStrengthRepository:
    return SqlIndustryStrengthRepository(session)


async def screener_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlScreenerRepository:
    return SqlScreenerRepository(session)


async def screener_query_service(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> ScreenerQueryService:
    return ScreenerQueryService(session)


def require_admin_key(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise AppError("UNAUTHORIZED", "Missing or invalid admin API key", 401)
