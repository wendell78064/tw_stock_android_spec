import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.adapters.shioaji_realtime_provider import SHIOAJI_SUBSCRIPTION_HARD_LIMIT
from app.core.settings import get_settings
from app.repositories.sql_alert import SqlAlertRepository
from app.repositories.sql_portfolio import SqlPortfolioRepository
from app.services.portfolio import PortfolioAccountingService
from app.services.realtime_alerts import RealtimeAlertEvaluationService

P2_WORST_CASE_ADDITION = 2


class ReadOnlyRedis:
    async def delete(self, _key: str) -> None:
        return None


def capacity_plan(
    p0_members: set[str],
    p1_members: set[str],
    budget: int | None,
    provider_limit: int = SHIOAJI_SUBSCRIPTION_HARD_LIMIT,
) -> dict[str, int | str]:
    unique_ticks = len(p0_members | p1_members)
    rollout_safe = (
        budget is not None
        and budget <= provider_limit
        and unique_ticks + P2_WORST_CASE_ADDITION <= budget
    )
    return {
        "P0_MEMBERS": len(p0_members),
        "P1_MEMBERS": len(p1_members),
        "P0_P1_UNIQUE_TICKS": unique_ticks,
        "P2_WORST_CASE_ADDITION": P2_WORST_CASE_ADDITION,
        "CURRENT_BUDGET": budget if budget is not None else "UNCONFIGURED",
        "PROVIDER_LIMIT": provider_limit,
        "ROLLOUT_SAFE": "YES" if rollout_safe else "NO",
    }


async def load_memberships(session) -> tuple[set[str], set[str]]:
    portfolios = SqlPortfolioRepository(session)
    accounting = PortfolioAccountingService()
    p0_members = set()
    available = await portfolios.list_portfolios()
    active = next(
        (item for item in available if item.is_default),
        available[0] if available else None,
    )
    if active is not None:
        positions = accounting.replay(await portfolios.list_transactions(active.id))
        p0_members.update(
            f"{position.security.market.value}:{position.security.code}"
            for position in positions
            if position.quantity_shares > 0
        )
    alerts = RealtimeAlertEvaluationService(ReadOnlyRedis(), SqlAlertRepository(session))
    await alerts.refresh()
    return p0_members, alerts.realtime_security_keys()


async def async_main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            p0_members, p1_members = await load_memberships(session)
        result = capacity_plan(
            p0_members, p1_members, settings.realtime_broker_subscription_budget
        )
        for key, value in result.items():
            print(f"{key}={value}")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
