from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, Request
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
from app.services.comparison import ComparisonService
from app.services.readiness import ReadinessChecker
from app.services.screener_query import ScreenerQueryService


async def comparison_service(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> ComparisonService:
    return ComparisonService(session)


def readiness_checker(request: Request) -> ReadinessChecker:
    return request.app.state.readiness_checker


def redis_client(request: Request) -> Redis:
    return request.app.state.redis


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


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


