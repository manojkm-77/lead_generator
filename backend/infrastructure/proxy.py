"""
Smart Proxy Rotation & Session Management.

Supports:
  - Static proxy list (round-robin / random)
  - Backconnect/residential proxy API integration
  - Per-session sticky proxies
  - Failure tracking and dead proxy eviction
"""

import asyncio
import logging
import random
import time
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

from backend.infrastructure.redis import get_redis, is_redis_available

logger = logging.getLogger(__name__)

_memory_proxy_pool: list[dict] = []
_memory_proxy_failures: dict[str, int] = {}
_memory_proxy_index: int = 0
_memory_sticky_sessions: dict[str, str] = {}


class ProxyRotator:
    def __init__(self):
        from backend.config import get_settings
        self.settings = get_settings()
        self._enabled = self.settings.proxy_enabled
        self._strategy = self.settings.proxy_rotation_strategy
        self._backconnect_url = self.settings.proxy_backconnect_url
        self._backconnect_api_key = self.settings.proxy_backconnect_api_key
        self._max_failures = 3
        self._ban_cooldown = 300
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            await self._load_proxy_list()
            self._initialized = True

    async def _load_proxy_list(self):
        raw = self.settings.proxy_list
        if raw:
            for entry in raw.split(","):
                entry = entry.strip()
                if not entry:
                    continue
                parts = entry.split("@") if "@" in entry else [entry]
                if len(parts) == 2:
                    user_pass, host_port = parts
                    username, password = user_pass.split(":", 1)
                    host, port = host_port.rsplit(":", 1)
                    proxy_url = f"http://{username}:{password}@{host}:{port}"
                elif len(parts) == 1:
                    host, port = entry.rsplit(":", 1)
                    proxy_url = f"http://{host}:{port}"
                else:
                    continue
                _memory_proxy_pool.append({
                    "url": proxy_url,
                    "failures": 0,
                    "banned_until": 0.0,
                    "last_used": 0.0,
                })
            logger.info("Loaded %d proxies from config", len(_memory_proxy_pool))
        r = await get_redis()
        if r and is_redis_available():
            stored = await r.smembers("bh:proxy:pool")
            for proxy_url in stored:
                if not any(p["url"] == proxy_url for p in _memory_proxy_pool):
                    _memory_proxy_pool.append({
                        "url": proxy_url,
                        "failures": 0,
                        "banned_until": 0.0,
                        "last_used": 0.0,
                    })

    async def get_proxy(self, url: str = "", session_id: str = "") -> Optional[dict]:
        if not self._enabled:
            return None
        await self._ensure_initialized()

        valid = [p for p in _memory_proxy_pool if time.time() >= p.get("banned_until", 0)]
        if not valid:
            logger.warning("No valid proxies available")
            return None

        if session_id and session_id in _memory_sticky_sessions:
            sticky = _memory_sticky_sessions[session_id]
            for p in valid:
                if p["url"] == sticky:
                    return dict(p)

        async with self._lock:
            if self._strategy == "round-robin":
                global _memory_proxy_index
                if _memory_proxy_index >= len(valid):
                    _memory_proxy_index = 0
                proxy = valid[_memory_proxy_index]
                _memory_proxy_index = (_memory_proxy_index + 1) % len(valid)
            elif self._strategy == "least-used":
                proxy = min(valid, key=lambda p: p.get("last_used", 0))
            else:
                proxy = random.choice(valid)

            proxy["last_used"] = time.time()
            if session_id:
                _memory_sticky_sessions[session_id] = proxy["url"]

            return dict(proxy)

    async def get_proxy_url(self, url: str = "", session_id: str = "") -> Optional[str]:
        proxy = await self.get_proxy(url, session_id)
        return proxy["url"] if proxy else None

    async def get_httpx_proxies(self, url: str = "", session_id: str = "") -> dict:
        proxy = await self.get_proxy(url, session_id)
        if proxy:
            return {"all://": proxy["url"]}
        return {}

    async def report_success(self, proxy_url: str):
        r = await get_redis()
        if r and is_redis_available():
            await r.hincrby("bh:proxy:stats", f"{proxy_url}:success", 1)
        for p in _memory_proxy_pool:
            if p["url"] == proxy_url:
                p["failures"] = 0
                break

    async def report_failure(self, proxy_url: str):
        r = await get_redis()
        if r and is_redis_available():
            key = f"bh:proxy:stats"
            failures = await r.hincrby(key, f"{proxy_url}:failures", 1)
            if failures >= self._max_failures:
                await r.hset(key, f"{proxy_url}:banned", str(time.time() + self._ban_cooldown))
        for p in _memory_proxy_pool:
            if p["url"] == proxy_url:
                p["failures"] += 1
                if p["failures"] >= self._max_failures:
                    p["banned_until"] = time.time() + self._ban_cooldown
                    logger.info("Proxy banned for %ds: %s", self._ban_cooldown, proxy_url)
                break

    async def add_proxy(self, proxy_url: str):
        r = await get_redis()
        if r and is_redis_available():
            await r.sadd("bh:proxy:pool", proxy_url)
        if not any(p["url"] == proxy_url for p in _memory_proxy_pool):
            _memory_proxy_pool.append({
                "url": proxy_url,
                "failures": 0,
                "banned_until": 0.0,
                "last_used": 0.0,
            })
            logger.info("Added proxy: %s", proxy_url)

    async def remove_proxy(self, proxy_url: str):
        r = await get_redis()
        if r and is_redis_available():
            await r.srem("bh:proxy:pool", proxy_url)
        _memory_proxy_pool[:] = [p for p in _memory_proxy_pool if p["url"] != proxy_url]

    async def get_backconnect_proxy(self) -> Optional[str]:
        if not self._backconnect_url:
            return None
        try:
            import httpx
            headers = {"Authorization": f"Bearer {self._backconnect_api_key}"} if self._backconnect_api_key else {}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self._backconnect_url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    proxy = data.get("proxy") or data.get("data", {}).get("proxy")
                    if proxy:
                        logger.debug("Fetched backconnect proxy: %s", proxy)
                        return proxy
        except Exception as e:
            logger.warning("Backconnect proxy fetch failed: %s", e)
        return None

    async def stats(self) -> dict:
        total = len(_memory_proxy_pool)
        active = sum(1 for p in _memory_proxy_pool if time.time() >= p.get("banned_until", 0))
        banned = total - active
        return {
            "enabled": self._enabled,
            "strategy": self._strategy,
            "total": total,
            "active": active,
            "banned": banned,
            "sticky_sessions": len(_memory_sticky_sessions),
        }

    async def flush(self):
        r = await get_redis()
        if r and is_redis_available():
            await r.delete("bh:proxy:pool", "bh:proxy:stats")
        _memory_proxy_pool.clear()
        _memory_proxy_failures.clear()
        _memory_proxy_index = 0
        _memory_sticky_sessions.clear()
        self._initialized = False
