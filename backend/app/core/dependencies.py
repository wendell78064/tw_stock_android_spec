from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_derivatives import SqlDerivativesRepository
from app.repositories.sql_market_spot import SqlMarketSpotRepository
from app.repositories.sql_portfolio import SqlPortfolioRepository
from app.repositories.sql_price import SqlPriceRepository
from app.repositories.sql_security import SqlSecurityRepository
from app.repositories.sql_watchlist import SqlWatchlistRepository
from app.services.readiness import ReadinessChecker


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
