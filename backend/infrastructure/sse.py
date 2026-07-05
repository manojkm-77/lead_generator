"""
SSE Live Stream Publisher.

Captures real-time worker metrics and broadcasts them to
all connected frontend clients via Server-Sent Events.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkerMetrics:
    jobs_processed: int = 0
    urls_discovered: int = 0
    urls_found: int = 0
    companies_saved: int = 0
    contacts_extracted: int = 0
    pages_fetched: int = 0
    errors: int = 0
    rate_limited: int = 0
    proxy_rotations: int = 0
    active_workers: int = 0
    queue_depth_search: int = 0
    queue_depth_url: int = 0
    started_at: float = field(default_factory=time.time)
    elapsed: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["elapsed"] = round(time.time() - self.started_at, 1)
        return d


class SSEPublisher:
    def __init__(self):
        self._metrics = WorkerMetrics()
        self._lock = asyncio.Lock()
        self._subscribers: set[asyncio.Queue] = set()
        self._event = asyncio.Event()

    async def publish(self, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._metrics, key):
                    setattr(self._metrics, key, value)
            self._event.set()
            self._event.clear()

        await self._broadcast()

    async def increment(self, **kwargs):
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._metrics, key):
                    current = getattr(self._metrics, key)
                    setattr(self._metrics, key, current + value)
            self._event.set()
            self._event.clear()

        await self._broadcast()

    async def _broadcast(self):
        data = json.dumps(self._metrics.to_dict())
        dead = set()
        for queue in self._subscribers:
            try:
                await asyncio.wait_for(queue.put(data), timeout=0.1)
            except asyncio.TimeoutError:
                dead.add(queue)
            except Exception as e:
                logger.warning("SSE broadcast error: %s", e)
                dead.add(queue)
        self._subscribers -= dead

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribers.add(queue)
        await queue.put(json.dumps(self._metrics.to_dict()))
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        self._subscribers.discard(queue)

    async def event_generator(self, queue: asyncio.Queue):
        try:
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps(self._metrics.to_dict())}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self.unsubscribe(queue)

    async def get_metrics(self) -> dict:
        async with self._lock:
            return self._metrics.to_dict()

    async def reset_metrics(self):
        async with self._lock:
            self._metrics = WorkerMetrics()


_sse_publisher: Optional[SSEPublisher] = None


def get_sse_publisher() -> SSEPublisher:
    global _sse_publisher
    if _sse_publisher is None:
        _sse_publisher = SSEPublisher()
    return _sse_publisher
