import asyncio
import logging
import subprocess
import sys
from datetime import datetime, timezone

from backend.database import async_session
from backend.models.company import Company
from backend.models.crawl_log import CrawlLog

logger = logging.getLogger(__name__)


class CrawlerService:
    SPIDER_REGISTRY = {
        "indiamart": "backend.spiders.indiamart",
        "justdial": "backend.spiders.justdial",
        "tradeindia": "backend.spiders.tradeindia",
        "googlemaps": "backend.spiders.googlemaps",
        "yellowpages": "backend.spiders.yellowpages",
        "exportersindia": "backend.spiders.exportersindia",
        "companywebsite": "backend.spiders.companywebsite",
        "linkedin_company": "backend.spiders.linkedin_company",
        "gst_directory": "backend.spiders.gst_directory",
    }

    @classmethod
    def available_spiders(cls) -> list[str]:
        return list(cls.SPIDER_REGISTRY.keys())

    @classmethod
    async def start_crawl(cls, spider_name: str, keywords: list[str], max_pages: int = 10) -> dict:
        if spider_name not in cls.SPIDER_REGISTRY:
            raise ValueError(f"Unknown spider: {spider_name}")

        async with async_session() as db:
            log = CrawlLog(
                spider_name=spider_name,
                start_time=datetime.now(timezone.utc),
                status="running",
            )
            db.add(log)
            await db.commit()
            await db.refresh(log)
            log_id = log.id

        logger.info(f"Crawl started: spider={spider_name}, keywords={keywords}, max_pages={max_pages}")

        # Run spider in background thread
        loop = asyncio.get_event_loop()
        asyncio.create_task(
            cls._run_spider_async(spider_name, keywords, max_pages, log_id)
        )

        return {
            "log_id": log_id,
            "spider_name": spider_name,
            "status": "started",
            "message": f"Crawl job queued for {spider_name}",
        }

    @classmethod
    async def _run_spider_async(cls, spider_name: str, keywords: list[str], max_pages: int, log_id: int):
        try:
            cmd = [
                sys.executable, "run_spider.py",
                "--spider", spider_name,
                "--max-pages", str(max_pages),
            ]
            if keywords:
                cmd.extend(["--queries"] + keywords)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                await cls.update_log(log_id, status="completed", end_time=datetime.now(timezone.utc))
                logger.info(f"Spider {spider_name} completed successfully")
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                await cls.update_log(
                    log_id,
                    status="failed",
                    end_time=datetime.now(timezone.utc),
                    errors=error_msg,
                )
                logger.error(f"Spider {spider_name} failed: {error_msg}")

        except Exception as e:
            await cls.update_log(
                log_id,
                status="failed",
                end_time=datetime.now(timezone.utc),
                errors=str(e),
            )
            logger.error(f"Spider {spider_name} failed: {e}")

    @classmethod
    async def update_log(cls, log_id: int, **kwargs):
        async with async_session() as db:
            log = await db.get(CrawlLog, log_id)
            if log:
                for key, value in kwargs.items():
                    if isinstance(value, datetime):
                        value = value.replace(tzinfo=None)
                    setattr(log, key, value)
                await db.commit()
