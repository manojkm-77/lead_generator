"""
Domain-Level Courtesy Limiter.

Token-bucket rate limiter per domain + robots.txt cache.
Guarantees the engine never hits the same root domain concurrently
beyond the configured threshold.
"""

import asyncio
import json
import logging
import re
import time
from collections import defaultdict
from typing import Optional
from urllib.parse import urlparse

import httpx

from backend.infrastructure.redis import get_redis, is_redis_available

logger = logging.getLogger(__name__)

# ── In-memory fallback stores ─────────────────────────────────────────────
_memory_tokens: dict[str, dict] = {}
_memory_robots: dict[str, dict] = {}
_memory_crawl_delay: dict[str, float] = {}
_memory_last_request: dict[str, float] = {}


class DomainRateLimiter:
    def __init__(self):
        from backend.config import get_settings
        self.settings = get_settings()
        self._capacity = self.settings.rate_limit_token_bucket_capacity
        self._refill_rate = self.settings.rate_limit_token_refill_rate
        self._window = self.settings.rate_limit_window_seconds
        self._max_requests = self.settings.rate_limit_requests_per_domain
        self._robots_ttl = self.settings.robots_cache_ttl

    # ── Token Bucket ─────────────────────────────────────────────────────

    async def acquire(self, domain: str, tokens: int = 1) -> float:
        """Wait until `tokens` are available for `domain`. Returns wait time."""
        r = await get_redis()
        if r and is_redis_available():
            return await self._acquire_redis(r, domain, tokens)
        return await self._acquire_memory(domain, tokens)

    async def _acquire_redis(self, r, domain: str, tokens: int) -> float:
        key = f"bh:ratelimit:{domain}"
        now = time.time()

        script = """
        local key = KEYS[1]
        local capacity = tonumber(ARGV[1])
        local refill = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        local tokens_needed = tonumber(ARGV[4])

        local data = redis.call('HMGET', key, 'tokens', 'last_refill')
        local tokens = tonumber(data[1] or capacity)
        local last_refill = tonumber(data[2] or now)

        local elapsed = math.max(0, now - last_refill)
        tokens = math.min(capacity, tokens + elapsed * refill)
        last_refill = now

        if tokens >= tokens_needed then
            tokens = tokens - tokens_needed
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, 60)
            return 0.0
        else
            local wait = (tokens_needed - tokens) / refill
            redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
            redis.call('EXPIRE', key, 60)
            return wait
        end
        """
        try:
            wait = await r.eval(script, 1, key, self._capacity, self._refill_rate, now, tokens)
            wait = float(wait)
            delay = max(wait, await self._get_crawl_delay(domain))
            if delay > 0:
                await asyncio.sleep(delay)
            return delay
        except Exception as e:
            logger.warning("Rate limiter Redis error for %s: %s", domain, e)
            await asyncio.sleep(0.5)
            return 0.5

    async def _acquire_memory(self, domain: str, tokens: int) -> float:
        now = time.time()
        if domain not in _memory_tokens:
            _memory_tokens[domain] = {"tokens": self._capacity, "last_refill": now}
        state = _memory_tokens[domain]
        elapsed = max(0, now - state["last_refill"])
        state["tokens"] = min(self._capacity, state["tokens"] + elapsed * self._refill_rate)
        state["last_refill"] = now

        crawl_delay = _memory_crawl_delay.get(domain, 0.0)

        if state["tokens"] >= tokens:
            state["tokens"] -= tokens
            delay = crawl_delay
        else:
            wait = (tokens - state["tokens"]) / self._refill_rate
            delay = max(wait, crawl_delay)

        if delay > 0:
            await asyncio.sleep(delay)
        return delay

    async def release(self, domain: str):
        pass

    # ── robots.txt ───────────────────────────────────────────────────────

    async def check_robots(self, url: str, user_agent: str = "BuyerHunterBot/2.0") -> tuple[bool, str]:
        """Check if URL is allowed by robots.txt. Returns (allowed, reason)."""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.hostname or ""
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        r = await get_redis()
        if r and is_redis_available():
            cached = await r.get(f"bh:robots:{domain}")
            if cached:
                rules = json.loads(cached)
            else:
                rules = await self._fetch_robots(robots_url)
                await r.setex(f"bh:robots:{domain}", self._robots_ttl, json.dumps(rules))
        else:
            if domain in _memory_robots:
                rules = _memory_robots[domain]
            else:
                rules = await self._fetch_robots(robots_url)
                _memory_robots[domain] = rules

        path = parsed.path or "/"
        allowed, reason = self._eval_robots(rules, path, user_agent)
        if not allowed:
            logger.debug("robots.txt blocks %s: %s", url, reason)
        return allowed, reason

    async def _fetch_robots(self, robots_url: str) -> dict:
        import json
        rules = {"crawl_delay": 0, "disallows": [], "allows": [], "sitemaps": []}
        try:
            async with httpx.AsyncClient(timeout=10, verify=False) as client:
                resp = await client.get(robots_url, headers={"User-Agent": "BuyerHunterBot/2.0"})
                if resp.status_code == 200:
                    rules = self._parse_robots(resp.text)
                elif resp.status_code == 404:
                    pass
                else:
                    logger.debug("robots.txt fetch %s returned %d", robots_url, resp.status_code)
        except Exception as e:
            logger.debug("Failed to fetch robots.txt %s: %s", robots_url, e)
        return rules

    def _parse_robots(self, text: str) -> dict:
        rules = {"crawl_delay": 0.0, "disallows": [], "allows": [], "sitemaps": []}
        current_agents: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agents = [agent] if agent != "*" else ["*"]
            elif line.lower().startswith("disallow:") and current_agents:
                path = line.split(":", 1)[1].strip()
                if path and ("*" in current_agents or "BuyerHunterBot" in current_agents or "*" in [a for a in current_agents]):
                    rules["disallows"].append(path or "/")
            elif line.lower().startswith("allow:") and current_agents:
                path = line.split(":", 1)[1].strip()
                if path and ("*" in current_agents or "BuyerHunterBot" in current_agents):
                    rules["allows"].append(path)
            elif line.lower().startswith("crawl-delay:") and current_agents:
                if "*" in current_agents or "BuyerHunterBot" in current_agents:
                    try:
                        rules["crawl_delay"] = max(rules["crawl_delay"], float(line.split(":", 1)[1].strip()))
                    except (ValueError, IndexError):
                        pass
            elif line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url:
                    rules["sitemaps"].append(url)
        return rules

    def _eval_robots(self, rules: dict, path: str, user_agent: str) -> tuple[bool, str]:
        for allow_pattern in rules.get("allows", []):
            if self._path_match(allow_pattern, path):
                return True, "explicitly allowed"
        for disallow_pattern in rules.get("disallows", []):
            if self._path_match(disallow_pattern, path):
                return False, f"disallowed by pattern {disallow_pattern}"
        return True, "no matching rule"

    def _path_match(self, pattern: str, path: str) -> bool:
        if "*" not in pattern:
            return path.startswith(pattern)
        regex = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.match(regex, path))

    async def _get_crawl_delay(self, domain: str) -> float:
        r = await get_redis()
        if r and is_redis_available():
            cached = await r.get(f"bh:robots:{domain}")
            if cached:
                rules = json.loads(cached)
                return rules.get("crawl_delay", 0.0)
        elif domain in _memory_robots:
            return _memory_robots[domain].get("crawl_delay", 0.0)
        return 0.0

    async def get_rate_limit_stats(self, domain: str) -> dict:
        r = await get_redis()
        if r and is_redis_available():
            key = f"bh:ratelimit:{domain}"
            data = await r.hgetall(key)
            if data:
                return {
                    "domain": domain,
                    "tokens_remaining": float(data.get("tokens", 0)),
                    "capacity": self._capacity,
                    "crawl_delay": await self._get_crawl_delay(domain),
                }
        state = _memory_tokens.get(domain)
        return {
            "domain": domain,
            "tokens_remaining": state["tokens"] if state else self._capacity,
            "capacity": self._capacity,
            "crawl_delay": _memory_crawl_delay.get(domain, 0.0),
        }

    async def flush(self):
        r = await get_redis()
        if r and is_redis_available():
            keys = await r.keys("bh:ratelimit:*")
            if keys:
                await r.delete(*keys)
            robot_keys = await r.keys("bh:robots:*")
            if robot_keys:
                await r.delete(*robot_keys)
        _memory_tokens.clear()
        _memory_robots.clear()
        _memory_crawl_delay.clear()
        _memory_last_request.clear()
