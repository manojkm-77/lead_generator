"""
Dual-Queue Task Broker — Redis-backed async queues.

Two isolated queues:
  1) SearchJobQueue    – high-level keyword/directory exploration (priority-weighted)
  2) URLDiscoveryQueue – individual target business URLs with deduplication
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from backend.infrastructure.redis import get_redis, is_redis_available

logger = logging.getLogger(__name__)

# ── In-memory fallback stores ─────────────────────────────────────────────
_memory_search_queue: list[dict] = []
_memory_search_processing: dict[str, dict] = {}
_memory_url_queue: list[dict] = []
_memory_url_seen: set[str] = set()
_memory_url_processing: dict[str, dict] = {}


# ═══════════════════════════════════════════════════════════════════════════
# Search Job Queue
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SearchJob:
    id: str = ""
    run_id: str = ""
    query: str = ""
    source: str = ""
    priority: int = 5
    max_pages: int = 3
    status: str = "queued"
    retry_count: int = 0
    max_retries: int = 3
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def key(self):
        return f"bh:search:job:{self.id}"

    def to_dict(self):
        d = asdict(self)
        d["metadata"] = json.dumps(self.metadata) if self.metadata else "{}"
        return d

    @classmethod
    def from_dict(cls, data: dict):
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except (json.JSONDecodeError, TypeError):
                data["metadata"] = {}
        return cls(**data)


class SearchJobQueue:
    KEY_QUEUE = "bh:search:queue"
    KEY_PROCESSING = "bh:search:processing"

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"bh:search:job:{job_id}"

    async def enqueue(self, job: SearchJob) -> str:
        if not job.id:
            job.id = f"sj_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}"
        if not job.created_at:
            job.created_at = time.time()
        job.status = "queued"

        r = await get_redis()
        if r and is_redis_available():
            await r.hset(job.key(), mapping=job.to_dict())
            await r.zadd(self.KEY_QUEUE, {job.id: job.priority})
        else:
            _memory_search_queue.append(job.to_dict())
            _memory_search_queue.sort(key=lambda j: -j.get("priority", 5))

        logger.debug("Enqueued search job %s: %s on %s", job.id, job.query, job.source)
        return job.id

    async def enqueue_batch(self, jobs: list[SearchJob]) -> list[str]:
        ids = []
        for job in jobs:
            ids.append(await self.enqueue(job))
        return ids

    async def dequeue(self, limit: int = 1) -> list[SearchJob]:
        r = await get_redis()
        if r and is_redis_available():
            results = await r.zpopmax(self.KEY_QUEUE, count=limit)
            jobs = []
            for job_id, score in results:
                raw = await r.hgetall(self._job_key(job_id))
                if not raw:
                    continue
                job = SearchJob.from_dict(raw)
                job.status = "running"
                job.started_at = time.time()
                await r.hset(job.key(), mapping=job.to_dict())
                await r.sadd(self.KEY_PROCESSING, job.id)
                jobs.append(job)
            return jobs
        else:
            acquired = []
            remaining = []
            now = time.time()
            for raw in _memory_search_queue:
                if len(acquired) >= limit:
                    remaining.append(raw)
                    continue
                if raw.get("status") == "queued":
                    raw["status"] = "running"
                    raw["started_at"] = now
                    job = SearchJob.from_dict(raw)
                    _memory_search_processing[job.id] = raw
                    acquired.append(job)
                else:
                    remaining.append(raw)
            _memory_search_queue.clear()
            _memory_search_queue.extend(remaining)
            return acquired

    async def complete(self, job_id: str):
        r = await get_redis()
        if r and is_redis_available():
            await r.hset(self._job_key(job_id), mapping={
                "status": "completed",
                "completed_at": str(time.time()),
            })
            await r.srem(self.KEY_PROCESSING, job_id)
        else:
            if job_id in _memory_search_processing:
                _memory_search_processing[job_id]["status"] = "completed"
                _memory_search_processing[job_id]["completed_at"] = time.time()

    async def fail(self, job_id: str, error: str = ""):
        r = await get_redis()
        if r and is_redis_available():
            raw = await r.hgetall(self._job_key(job_id))
            job = SearchJob.from_dict(raw) if raw else None
            if job and job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = "queued"
                job.error = error
                await r.hset(job.key(), mapping=job.to_dict())
                await r.zadd(self.KEY_QUEUE, {job.id: job.priority})
                logger.info("Search job %s requeued (retry %d/%d)", job_id, job.retry_count, job.max_retries)
            else:
                await r.hset(self._job_key(job_id), mapping={
                    "status": "failed",
                    "error": error,
                    "completed_at": str(time.time()),
                })
                logger.warning("Search job %s failed permanently: %s", job_id, error)
            await r.srem(self.KEY_PROCESSING, job_id)
        else:
            if job_id in _memory_search_processing:
                j = _memory_search_processing[job_id]
                if j.get("retry_count", 0) < j.get("max_retries", 3):
                    j["retry_count"] += 1
                    j["status"] = "queued"
                    j["error"] = error
                    _memory_search_queue.append(j)
                    _memory_search_queue.sort(key=lambda x: -x.get("priority", 5))
                else:
                    j["status"] = "failed"
                    j["error"] = error
                    j["completed_at"] = time.time()
                del _memory_search_processing[job_id]

    async def stats(self) -> dict:
        r = await get_redis()
        if r and is_redis_available():
            queued = await r.zcard(self.KEY_QUEUE)
            processing = await r.scard(self.KEY_PROCESSING)
            return {"queued": queued, "running": processing}
        return {
            "queued": len(_memory_search_queue),
            "running": len(_memory_search_processing),
        }

    async def flush(self):
        r = await get_redis()
        if r and is_redis_available():
            keys = await r.keys("bh:search:*")
            if keys:
                await r.delete(*keys)
        _memory_search_queue.clear()
        _memory_search_processing.clear()


# ═══════════════════════════════════════════════════════════════════════════
# URL Discovery Queue
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class URLDiscoveryJob:
    id: str = ""
    url: str = ""
    domain: str = ""
    source: str = ""
    source_job_id: str = ""
    source_query: str = ""
    status: str = "queued"
    retry_count: int = 0
    max_retries: int = 3
    discovered_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        d = asdict(self)
        d["metadata"] = json.dumps(self.metadata) if self.metadata else "{}"
        return d

    @classmethod
    def from_dict(cls, data: dict):
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except (json.JSONDecodeError, TypeError):
                data["metadata"] = {}
        return cls(**data)


class URLDiscoveryQueue:
    KEY_QUEUE = "bh:url:queue"
    KEY_SEEN = "bh:url:seen"
    KEY_PROCESSING = "bh:url:processing"

    def _meta_key(self, url_hash: str) -> str:
        return f"bh:url:meta:{url_hash}"

    def _url_hash(self, url: str) -> str:
        import hashlib
        normalized = url.strip().rstrip("/").lower()
        return hashlib.md5(normalized.encode()).hexdigest()

    async def ingest(self, url: str, source: str = "", source_job_id: str = "",
                     source_query: str = "", **metadata) -> Optional[str]:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.hostname or ""

        url_hash = self._url_hash(url)
        r = await get_redis()

        if r and is_redis_available():
            already_seen = await r.sismember(self.KEY_SEEN, url_hash)
            if already_seen:
                logger.debug("URL already in queue: %s", url)
                return None
            await r.sadd(self.KEY_SEEN, url_hash)
        else:
            if url_hash in _memory_url_seen:
                logger.debug("URL already in queue (mem): %s", url)
                return None
            _memory_url_seen.add(url_hash)

        job = URLDiscoveryJob(
            id=f"uj_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}",
            url=url,
            domain=domain,
            source=source,
            source_job_id=source_job_id,
            source_query=source_query,
            discovered_at=time.time(),
            metadata=metadata,
        )

        if r and is_redis_available():
            await r.hset(self._meta_key(url_hash), mapping=job.to_dict())
            await r.rpush(self.KEY_QUEUE, url_hash)
        else:
            _memory_url_queue.append({"url_hash": url_hash, "job": job.to_dict()})

        logger.debug("Ingested URL: %s (domain=%s, source=%s)", url, domain, source)
        return job.id

    async def ingest_batch(self, urls: list[str], source: str = "",
                           source_job_id: str = "", source_query: str = "") -> list[str]:
        inserted = []
        for url in urls:
            job_id = await self.ingest(url, source, source_job_id, source_query)
            if job_id:
                inserted.append(job_id)
        return inserted

    async def dequeue(self, limit: int = 1) -> list[URLDiscoveryJob]:
        r = await get_redis()
        if r and is_redis_available():
            url_hashes = await r.lpop(self.KEY_QUEUE, count=limit)
            if not url_hashes:
                return []
            jobs = []
            for url_hash in url_hashes:
                raw = await r.hgetall(self._meta_key(url_hash))
                if not raw:
                    continue
                job = URLDiscoveryJob.from_dict(raw)
                job.status = "running"
                job.started_at = time.time()
                await r.hset(self._meta_key(url_hash), mapping=job.to_dict())
                await r.sadd(self.KEY_PROCESSING, url_hash)
                jobs.append(job)
            return jobs
        else:
            acquired = []
            remaining = []
            now = time.time()
            for entry in _memory_url_queue:
                if len(acquired) >= limit:
                    remaining.append(entry)
                    continue
                job = URLDiscoveryJob.from_dict(entry["job"])
                job.status = "running"
                job.started_at = now
                _memory_url_processing[entry["url_hash"]] = job.to_dict()
                acquired.append(job)
            _memory_url_queue.clear()
            _memory_url_queue.extend(remaining)
            return acquired

    async def complete(self, url_hash: str):
        r = await get_redis()
        if r and is_redis_available():
            await r.hset(self._meta_key(url_hash), mapping={
                "status": "completed",
                "completed_at": str(time.time()),
            })
            await r.srem(self.KEY_PROCESSING, url_hash)
        else:
            if url_hash in _memory_url_processing:
                _memory_url_processing[url_hash]["status"] = "completed"
                _memory_url_processing[url_hash]["completed_at"] = time.time()
                del _memory_url_processing[url_hash]

    async def fail(self, url_hash: str, error: str = ""):
        r = await get_redis()
        if r and is_redis_available():
            raw = await r.hgetall(self._meta_key(url_hash))
            job = URLDiscoveryJob.from_dict(raw) if raw else None
            if job and job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = "queued"
                job.error = error
                await r.hset(self._meta_key(url_hash), mapping=job.to_dict())
                await r.rpush(self.KEY_QUEUE, url_hash)
                logger.info("URL job %s requeued (retry %d/%d)", url_hash, job.retry_count, job.max_retries)
            else:
                await r.hset(self._meta_key(url_hash), mapping={
                    "status": "failed",
                    "error": error,
                    "completed_at": str(time.time()),
                })
            await r.srem(self.KEY_PROCESSING, url_hash)
        else:
            if url_hash in _memory_url_processing:
                j = _memory_url_processing[url_hash]
                if j.get("retry_count", 0) < j.get("max_retries", 3):
                    j["retry_count"] += 1
                    j["status"] = "queued"
                    j["error"] = error
                    _memory_url_queue.append({"url_hash": url_hash, "job": j})
                else:
                    j["status"] = "failed"
                    j["error"] = error
                    j["completed_at"] = time.time()
                del _memory_url_processing[url_hash]

    async def dedup_count(self) -> int:
        r = await get_redis()
        if r and is_redis_available():
            return await r.scard(self.KEY_SEEN)
        return len(_memory_url_seen)

    async def queue_depth(self) -> int:
        r = await get_redis()
        if r and is_redis_available():
            return await r.llen(self.KEY_QUEUE)
        return len(_memory_url_queue)

    async def stats(self) -> dict:
        r = await get_redis()
        if r and is_redis_available():
            queued = await r.llen(self.KEY_QUEUE)
            processing = await r.scard(self.KEY_PROCESSING)
            dedup = await r.scard(self.KEY_SEEN)
            return {"queued": queued, "running": processing, "dedup_count": dedup}
        return {
            "queued": len(_memory_url_queue),
            "running": len(_memory_url_processing),
            "dedup_count": len(_memory_url_seen),
        }

    async def flush(self):
        r = await get_redis()
        if r and is_redis_available():
            keys = await r.keys("bh:url:*")
            if keys:
                await r.delete(*keys)
        _memory_url_queue.clear()
        _memory_url_seen.clear()
        _memory_url_processing.clear()
