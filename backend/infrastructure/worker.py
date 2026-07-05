"""
Discovery Worker Orchestrator.

Async distributed worker pool that pulls URLs from the URL Discovery Queue,
respects domain-level rate limits, rotates proxies, generates anti-fingerprint
headers, and reports metrics via SSE.

Flow:
  Worker → dequeue URL → check robots → acquire rate-limit token →
  get proxy → generate headers → fetch page → extract → save → report
"""

import asyncio
import json
import logging
import time
from typing import Optional
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

from backend.infrastructure.queue import URLDiscoveryQueue, SearchJobQueue
from backend.infrastructure.rate_limiter import DomainRateLimiter
from backend.infrastructure.proxy import ProxyRotator
from backend.infrastructure.headers import HeaderGenerator
from backend.infrastructure.retry import RetryManager
from backend.infrastructure.sse import get_sse_publisher, SSEPublisher

logger = logging.getLogger(__name__)


class URLProcessor:
    """Extracts company data from a single URL."""

    @staticmethod
    def extract_emails(text: str) -> list[str]:
        import re
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        return list(set(re.findall(pattern, text)))

    @staticmethod
    def extract_phones(text: str) -> list[str]:
        import re
        pattern = r"(?:\+91|0)?[ -]?[6-9]\d{9}"
        return list(set(re.findall(pattern, text)))

    @staticmethod
    def extract_company_name(soup: BeautifulSoup, url: str) -> str:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = parsed.netloc or parsed.hostname or ""
        base = base.replace("www.", "").split(".")[0]
        title_tag = soup.find("title")
        if title_tag and title_tag.text.strip():
            parts = title_tag.text.strip().split("|")[0].split("-")[0].strip()
            if len(parts) > 1:
                return parts
            return parts
        return base.replace(".", " ").title()

    @staticmethod
    def extract_description(soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:500]
        return ""

    @staticmethod
    def extract_social_links(soup: BeautifulSoup, base_url: str) -> dict:
        social = {}
        for a in soup.find_all("a", href=True):
            href = a["href"].lower()
            if "linkedin.com/company" in href:
                social["linkedin"] = href
            elif "facebook.com" in href:
                social["facebook"] = href
            elif "twitter.com" in href or "x.com" in href:
                social["twitter"] = href
            elif "instagram.com" in href:
                social["instagram"] = href
        return social


class DiscoveryWorker:
    def __init__(
        self,
        url_queue: Optional[URLDiscoveryQueue] = None,
        search_queue: Optional[SearchJobQueue] = None,
        rate_limiter: Optional[DomainRateLimiter] = None,
        proxy_rotator: Optional[ProxyRotator] = None,
        header_generator: Optional[HeaderGenerator] = None,
        retry_manager: Optional[RetryManager] = None,
        sse_publisher: Optional[SSEPublisher] = None,
        concurrency: int = 8,
        poll_interval: float = 1.0,
        batch_size: int = 5,
    ):
        from backend.config import get_settings
        self.settings = get_settings()

        self.url_queue = url_queue or URLDiscoveryQueue()
        self.search_queue = search_queue or SearchJobQueue()
        self.rate_limiter = rate_limiter or DomainRateLimiter()
        self.proxy_rotator = proxy_rotator or ProxyRotator()
        self.header_generator = header_generator or HeaderGenerator()
        self.retry_manager = retry_manager or RetryManager()
        self.sse = sse_publisher or get_sse_publisher()

        self._concurrency = concurrency
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        if self._running:
            logger.warning("Worker pool already running")
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(self._concurrency)
        ]
        logger.info("Started %d discovery workers", self._concurrency)

    async def stop(self):
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Stopped %d discovery workers", self._concurrency)

    async def _worker_loop(self, worker_id: int):
        logger.debug("Worker %d started", worker_id)
        while self._running:
            try:
                await self._process_batch(worker_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Worker %d error: %s", worker_id, e, exc_info=True)
                await asyncio.sleep(1)
        logger.debug("Worker %d stopped", worker_id)

    async def _process_batch(self, worker_id: int):
        jobs = await self.url_queue.dequeue(limit=self._batch_size)
        if not jobs:
            await asyncio.sleep(self._poll_interval)
            return

        await self.sse.increment(active_workers=1)

        for job in jobs:
            try:
                await self._process_url(worker_id, job)
            except Exception as e:
                logger.error("Worker %d failed to process %s: %s", worker_id, job.url, e)
                url_hash = job.url.encode() if not job.id else job.id
                try:
                    await self.url_queue.fail(job.id if job.id else str(hash(job.url)), str(e))
                except Exception:
                    pass
                await self.sse.increment(errors=1)

        await self.sse.increment(active_workers=-1)

    async def _process_url(self, worker_id: int, job):
        from backend.database import async_session
        from backend.models.company import Company

        parsed = urlparse(job.url)
        domain = parsed.netloc or parsed.hostname or ""

        allowed, reason = await self.rate_limiter.check_robots(job.url)
        if not allowed:
            logger.info("Worker %d skipped %s (robots.txt: %s)", worker_id, job.url, reason)
            await self.url_queue.complete(job.id)
            return

        await self.rate_limiter.acquire(domain)

        proxy = await self.proxy_rotator.get_proxy(job.url)
        if proxy:
            await self.sse.increment(proxy_rotations=1)

        headers = self.header_generator.generate()

        fetch_start = time.time()
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.http_request_timeout,
                follow_redirects=True,
                max_redirects=self.settings.http_max_redirects,
                verify=self.settings.http_verify_ssl,
                proxies=await self.proxy_rotator.get_httpx_proxies(job.url) if proxy else None,
            ) as client:
                response = await client.get(job.url, headers=headers)

            fetch_time = time.time() - fetch_start
            logger.debug("Worker %d fetched %s (%d) in %.1fs",
                          worker_id, job.url, response.status_code, fetch_time)

            if response.status_code >= 400:
                raise httpx.HTTPStatusError(f"HTTP {response.status_code}", request=response.request, response=response)

            if proxy:
                await self.proxy_rotator.report_success(proxy["url"])

            soup = BeautifulSoup(response.text, "lxml")
            company_name = URLProcessor.extract_company_name(soup, job.url)
            emails = URLProcessor.extract_emails(response.text)
            phones = URLProcessor.extract_phones(response.text)
            description = URLProcessor.extract_description(soup)
            social = URLProcessor.extract_social_links(soup, job.url)

            contacts_extracted = len(emails) + len(phones)

            async with async_session() as db:
                existing = await db.execute(
                    select(Company).where(Company.website == job.url)
                )
                existing_company = existing.scalar_one_or_none()

                if existing_company:
                    logger.debug("Worker %d found existing company for %s", worker_id, job.url)
                    if emails and not existing_company.email:
                        existing_company.email = emails[0]
                    if phones and not existing_company.phone:
                        existing_company.phone = phones[0]
                    await db.commit()
                    await self.sse.increment(companies_saved=0)
                else:
                    company = Company(
                        company_name=company_name[:255],
                        website=job.url[:500],
                        email=emails[0] if emails else "",
                        phone=phones[0] if phones else "",
                        about_us=description,
                        source=job.source or "discovery_worker",
                        source_url=job.url,
                        city=job.metadata.get("city", ""),
                        state=job.metadata.get("state", ""),
                        industry=job.metadata.get("industry", ""),
                    )
                    db.add(company)
                    await db.commit()
                    await self.sse.increment(companies_saved=1)

            await self.url_queue.complete(job.id)
            await self.sse.increment(
                jobs_processed=1,
                pages_fetched=1,
                contacts_extracted=contacts_extracted,
                urls_found=1,
            )

        except httpx.TimeoutException:
            logger.warning("Worker %d timeout fetching %s", worker_id, job.url)
            await self._handle_fetch_failure(worker_id, job, "timeout")
        except httpx.HTTPStatusError as e:
            logger.warning("Worker %d HTTP error %d for %s", worker_id, e.response.status_code, job.url)
            if e.response.status_code == 429:
                await self.sse.increment(rate_limited=1)
            await self._handle_fetch_failure(worker_id, job, f"http_{e.response.status_code}")
        except httpx.RequestError as e:
            logger.warning("Worker %d network error for %s: %s", worker_id, job.url, e)
            await self._handle_fetch_failure(worker_id, job, "network_error")
        except Exception as e:
            logger.error("Worker %d unexpected error for %s: %s", worker_id, job.url, e)
            await self._handle_fetch_failure(worker_id, job, "internal_error")

    async def _handle_fetch_failure(self, worker_id: int, job, error_type: str):
        import hashlib
        job_id = job.id if job.id else hashlib.md5(job.url.encode()).hexdigest()

        should_retry = await self.retry_manager.should_retry(job_id)
        if should_retry:
            await self.retry_manager.record_attempt(job_id)
            await self.retry_manager.wait(job_id)
            await self.url_queue.fail(job.id if job.id else job_id, error_type)
        else:
            await self.retry_manager.mark_permanent(job_id)
            await self.url_queue.fail(job.id if job.id else job_id, f"permanent_{error_type}")

        await self.sse.increment(errors=1)

    async def stats(self) -> dict:
        url_stats = await self.url_queue.stats()
        search_stats = await self.search_queue.stats()
        rate_stats = {}  # domain-specific
        proxy_stats = await self.proxy_rotator.stats()
        retry_stats = await self.retry_manager.stats()
        metrics = await self.sse.get_metrics()

        return {
            "running": self._running,
            "workers": {
                "configured": self._concurrency,
                "active": metrics.get("active_workers", 0),
            },
            "queues": {
                "search": search_stats,
                "url": url_stats,
            },
            "proxy": proxy_stats,
            "retry": retry_stats,
            "metrics": metrics,
        }

    async def health(self) -> dict:
        return {
            "status": "healthy" if self._running else "stopped",
            "workers": self._concurrency,
            "running": self._running,
        }
