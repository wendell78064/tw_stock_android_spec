from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class ReadinessChecker:
    def __init__(self, engine: AsyncEngine, redis: Redis):
        self.engine = engine
        self.redis = redis

    async def check(self) -> dict[str, str]:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        await self.redis.ping()
        return {"postgres": "ok", "redis": "ok"}
