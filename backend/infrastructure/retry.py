"""
Exponential Backoff Retry Manager.

Tracks retry state per job and computes progressive delays
with full-jitter to avoid thundering herd problems.
"""

import asyncio
import logging
import random
import time
from typing import Optional

from backend.infrastructure.redis import get_redis, is_redis_available

logger = logging.getLogger(__name__)

_memory_retry: dict[str, dict] = {}


class RetryManager:
    def __init__(self):
        from backend.config import get_settings
        self.settings = get_settings()
        self._max_attempts = self.settings.retry_max_attempts
        self._base_delay = self.settings.retry_base_delay_seconds
        self._max_delay = self.settings.retry_max_delay_seconds
        self._jitter = self.settings.retry_jitter_factor

    async def record_attempt(self, job_id: str) -> int:
        """Record a retry attempt. Returns attempt number (1-based)."""
        r = await get_redis()
        if r and is_redis_available():
            key = f"bh:retry:{job_id}"
            attempts = await r.hincrby(key, "attempts", 1)
            await r.hset(key, "last_attempt", str(time.time()))
            await r.expire(key, 86400)
            return attempts
        else:
            if job_id not in _memory_retry:
                _memory_retry[job_id] = {"attempts": 0, "last_attempt": 0}
            _memory_retry[job_id]["attempts"] += 1
            _memory_retry[job_id]["last_attempt"] = time.time()
            return _memory_retry[job_id]["attempts"]

    async def get_attempts(self, job_id: str) -> int:
        r = await get_redis()
        if r and is_redis_available():
            val = await r.hget(f"bh:retry:{job_id}", "attempts")
            return int(val) if val else 0
        state = _memory_retry.get(job_id)
        return state["attempts"] if state else 0

    async def should_retry(self, job_id: str) -> bool:
        attempts = await self.get_attempts(job_id)
        return attempts < self._max_attempts

    async def get_delay(self, job_id: str) -> float:
        """Compute delay before next retry using exponential backoff + full-jitter."""
        attempts = await self.get_attempts(job_id)
        if attempts == 0:
            return 0.0

        # Exponential backoff: base * 2^(attempts-1)
        delay = min(self._base_delay * (2 ** (attempts - 1)), self._max_delay)

        # Full-jitter: random between 0 and delay
        jittered = delay * (1 - self._jitter + random.random() * self._jitter * 2)
        jittered = max(jittered, 0.1)

        logger.debug("Retry delay for %s (attempt %d/%d): %.1fs",
                      job_id, attempts, self._max_attempts, jittered)
        return jittered

    async def wait(self, job_id: str):
        """Wait appropriate time before next retry."""
        delay = await self.get_delay(job_id)
        if delay > 0:
            await asyncio.sleep(delay)

    async def mark_permanent(self, job_id: str):
        """Mark job as permanently failed (max retries exceeded)."""
        r = await get_redis()
        if r and is_redis_available():
            key = f"bh:retry:{job_id}"
            await r.hset(key, "permanent", "1")
            await r.expire(key, 86400)
        if job_id in _memory_retry:
            _memory_retry[job_id]["permanent"] = True

    async def is_permanent(self, job_id: str) -> bool:
        r = await get_redis()
        if r and is_redis_available():
            val = await r.hget(f"bh:retry:{job_id}", "permanent")
            return val == "1"
        state = _memory_retry.get(job_id)
        return bool(state and state.get("permanent"))

    async def reset(self, job_id: str):
        """Reset retry state (e.g., after successful retry)."""
        r = await get_redis()
        if r and is_redis_available():
            await r.delete(f"bh:retry:{job_id}")
        _memory_retry.pop(job_id, None)

    async def stats(self) -> dict:
        r = await get_redis()
        active = 0
        if r and is_redis_available():
            keys = await r.keys("bh:retry:*")
            active = len(keys) if keys else 0
        else:
            active = len(_memory_retry)
        return {
            "max_attempts": self._max_attempts,
            "base_delay": self._base_delay,
            "max_delay": self._max_delay,
            "active_jobs": active,
        }

    async def flush(self):
        r = await get_redis()
        if r and is_redis_available():
            keys = await r.keys("bh:retry:*")
            if keys:
                await r.delete(*keys)
        _memory_retry.clear()
