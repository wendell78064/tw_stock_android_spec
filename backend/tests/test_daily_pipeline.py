from datetime import date
from unittest.mock import patch

import pytest

from app.cli.run_daily_pipeline import DailyPipelineRunner, execute_step_with_retry
from app.core.job_lock import JobLock, distributed_job_lock


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def get(self, key):
        return self.data.get(key)

    async def eval(self, script, numkeys, key, token):
        del script, numkeys
        if self.data.get(key) == token:
            del self.data[key]
            return 1
        return 0

    async def scan_iter(self, pattern):
        for k in list(self.data.keys()):
            yield k

    async def delete(self, *keys):
        count = 0
        for k in keys:
            if k in self.data:
                del self.data[k]
                count += 1
        return count

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_job_lock_acquire_and_release() -> None:
    fake_redis = FakeRedis()
    lock1 = JobLock(fake_redis, "test-job", ttl_seconds=60)
    lock2 = JobLock(fake_redis, "test-job", ttl_seconds=60)

    assert await lock1.acquire() is True
    assert await lock2.acquire() is False  # Second acquisition blocked

    # Owner-safe release
    assert await lock2.release() is False  # lock2 is not the owner
    assert await lock1.release() is True   # lock1 is owner and releases

    # Now lock2 can acquire
    assert await lock2.acquire() is True
    await lock2.release()


@pytest.mark.asyncio
async def test_distributed_job_lock_context_manager() -> None:
    fake_redis = FakeRedis()
    async with distributed_job_lock(fake_redis, "cm-job") as acquired1:
        assert acquired1 is True
        async with distributed_job_lock(fake_redis, "cm-job") as acquired2:
            assert acquired2 is False

    # After context exit, lock is released
    async with distributed_job_lock(fake_redis, "cm-job") as acquired3:
        assert acquired3 is True


@pytest.mark.asyncio
async def test_execute_step_with_retry() -> None:
    calls = 0

    async def flaky_fn():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("transient network drop")
        return "success"

    res = await execute_step_with_retry(flaky_fn, max_retries=1, backoff_seconds=0.01)
    assert res == "success"
    assert calls == 2


@pytest.mark.asyncio
async def test_pipeline_weekend_skip() -> None:
    # 2026-08-22 is Saturday
    weekend_date = date(2026, 8, 22)
    runner = DailyPipelineRunner(weekend_date, provider_type="fake")
    results = await runner.run(skip_lock=True)
    assert len(results) == 1
    assert results[0].status == "SKIPPED"
    assert "Weekend" in results[0].summary


@pytest.mark.asyncio
async def test_pipeline_already_running_lock() -> None:
    fake_redis = FakeRedis()
    # Pre-lock
    await fake_redis.set("twml:lock:daily-pipeline", "other_runner")

    with patch("app.cli.run_daily_pipeline.Redis.from_url", return_value=fake_redis):
        runner = DailyPipelineRunner(date(2026, 8, 18), provider_type="fake")
        results = await runner.run(skip_lock=False)
        assert len(results) == 1
        assert results[0].name == "JOB_LOCK"
        assert results[0].status == "SKIPPED"
