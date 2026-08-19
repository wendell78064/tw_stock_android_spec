from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import uuid

from redis.asyncio import Redis

RELEASE_LOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class JobLock:
    def __init__(self, redis: Redis, name: str, ttl_seconds: int = 1800):
        self.redis = redis
        self.key = f"twml:lock:{name}"
        self.ttl = ttl_seconds
        self.token = str(uuid.uuid4())

    async def acquire(self) -> bool:
        result = await self.redis.set(self.key, self.token, ex=self.ttl, nx=True)
        return bool(result)

    async def release(self) -> bool:
        try:
            result = await self.redis.eval(RELEASE_LOCK_LUA, 1, self.key, self.token)
            return bool(result)
        except Exception:
            return False


@asynccontextmanager
async def distributed_job_lock(
    redis: Redis, name: str, ttl_seconds: int = 1800
) -> AsyncIterator[bool]:
    lock = JobLock(redis, name, ttl_seconds)
    acquired = await lock.acquire()
    try:
        yield acquired
    finally:
        if acquired:
            await lock.release()
