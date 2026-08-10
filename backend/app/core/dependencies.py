from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.sql_security import SqlSecurityRepository
from app.services.readiness import ReadinessChecker


def readiness_checker(request: Request) -> ReadinessChecker:
    return request.app.state.readiness_checker


async def database_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


async def security_repository(
    session: Annotated[AsyncSession, Depends(database_session)],
) -> SqlSecurityRepository:
    return SqlSecurityRepository(session)
