"""
BuyerHunter AI — Spider Manager

Orchestrates multiple spiders with scheduling, resume, and reporting.
"""

import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SpiderManager:
    """Manages spider execution, scheduling, and reporting."""

    SPIDER_REGISTRY = {
        # Public Business Directories
        "indiamart": {
            "module": "backend.spiders.indiamart",
            "type": "directory",
            "description": "IndiaMART B2B directory",
        },
        "justdial": {
            "module": "backend.spiders.justdial",
            "type": "directory",
            "description": "JustDial local business directory",
        },
        "tradeindia": {
            "module": "backend.spiders.tradeindia",
            "type": "directory",
            "description": "TradeIndia trade directory",
        },
        "yellowpages": {
            "module": "backend.spiders.yellowpages",
            "type": "directory",
            "description": "Yellow Pages business directory",
        },
        "exportersindia": {
            "module": "backend.spiders.exportersindia",
            "type": "directory",
            "description": "ExportersIndia export/import directory",
        },
        # Company Websites
        "companywebsite": {
            "module": "backend.spiders.companywebsite",
            "type": "website",
            "description": "Direct company website crawler",
        },
        # Trade Associations
        "tradeassociation": {
            "module": "backend.spiders.tradeassociation",
            "type": "association",
            "description": "Trade association member directories",
        },
        # Government Directories
        "gst_directory": {
            "module": "backend.spiders.gst_directory",
            "type": "government",
            "description": "GST public directory",
        },
        # Trade Exhibitions
        "tradeexhibition": {
            "module": "backend.spiders.tradeexhibition",
            "type": "exhibition",
            "description": "Trade exhibition exhibitor lists",
        },
        # Maps & Social
        "googlemaps": {
            "module": "backend.spiders.googlemaps",
            "type": "maps",
            "description": "Google Maps business listings",
        },
        "linkedin": {
            "module": "backend.spiders.linkedin_company",
            "type": "social",
            "description": "LinkedIn company pages",
        },
    }

    STATE_DIR = Path("crawl_state")
    REPORTS_DIR = Path("crawl_reports")

    def __init__(self):
        self.STATE_DIR.mkdir(exist_ok=True)
        self.REPORTS_DIR.mkdir(exist_ok=True)
        self._running = {}

    @classmethod
    def available_spiders(cls) -> dict:
        return {
            name: info["description"]
            for name, info in cls.SPIDER_REGISTRY.items()
        }

    @classmethod
    def get_spider_types(cls) -> dict:
        types = {}
        for name, info in cls.SPIDER_REGISTRY.items():
            spider_type = info["type"]
            if spider_type not in types:
                types[spider_type] = []
            types[spider_type].append(name)
        return types

    async def run_spider(
        self,
        spider_name: str,
        queries: list[str] = None,
        max_pages: int = 5,
        urls: list[str] = None,
    ) -> dict:
        """Run a single spider and return results."""
        if spider_name not in self.SPIDER_REGISTRY:
            raise ValueError(f"Unknown spider: {spider_name}")

        if spider_name in self._running:
            # Clean stale entries older than 5 minutes
            age = (datetime.now(timezone.utc) - self._running[spider_name]).seconds
            if age > 300:
                logger.warning(f"Cleaning stale lock for {spider_name} (age={age}s)")
                self._running.pop(spider_name)
            else:
                return {"status": "already_running", "spider": spider_name}

        state_file = self.STATE_DIR / f"{spider_name}.json"
        start_state = self._load_state(state_file)

        logger.info(f"Starting spider: {spider_name}")
        self._running[spider_name] = datetime.now(timezone.utc)

        try:
            cmd = [
                sys.executable, "-m", "scrapy", "crawl", spider_name,
            ]

            if queries:
                cmd.extend(["-a", f"queries={json.dumps(queries)}"])
            if max_pages:
                cmd.extend(["-a", f"max_pages={max_pages}"])
            if urls:
                cmd.extend(["-a", f"urls={json.dumps(urls)}"])

            cmd.extend([
                "-s", "LOG_FILE=crawl_logs/{}_{}.log".format(
                    spider_name, datetime.now().strftime("%Y%m%d_%H%M%S")
                ),
            ])

            cwd = str(Path(__file__).resolve().parent.parent.parent)

            def _run_sync():
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    timeout=300,
                )
                return proc.returncode, proc.stdout, proc.stderr

            loop = asyncio.get_event_loop()
            return_code, stdout, stderr = await loop.run_in_executor(None, _run_sync)

            result = {
                "spider": spider_name,
                "status": "completed" if return_code == 0 else "failed",
                "return_code": return_code,
                "stdout": stdout[-2000:] if stdout else "",
                "stderr": stderr[-2000:] if stderr else "",
                "duration": (datetime.now(timezone.utc) - self._running[spider_name]).seconds,
            }

            self._save_state(state_file, result)
            return result

        except Exception as e:
            logger.error(f"Spider {spider_name} failed: {e}")
            return {
                "spider": spider_name,
                "status": "error",
                "error": str(e),
            }
        finally:
            self._running.pop(spider_name, None)

    async def run_multiple(
        self,
        spider_names: list[str],
        queries: list[str] = None,
        max_pages: int = 5,
        parallel: bool = False,
    ) -> list[dict]:
        """Run multiple spiders sequentially or in parallel."""
        if parallel:
            tasks = [
                self.run_spider(name, queries, max_pages)
                for name in spider_names
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = []
            for name in spider_names:
                result = await self.run_spider(name, queries, max_pages)
                results.append(result)
            return results

    async def run_all(self, queries: list[str] = None, max_pages: int = 3) -> list[dict]:
        """Run all registered spiders."""
        spider_names = list(self.SPIDER_REGISTRY.keys())
        return await self.run_multiple(spider_names, queries, max_pages)

    def get_state(self, spider_name: str) -> dict:
        """Get the last state of a spider."""
        state_file = self.STATE_DIR / f"{spider_name}.json"
        return self._load_state(state_file)

    def get_running(self) -> list[str]:
        """Get list of currently running spiders."""
        return list(self._running.keys())

    def generate_report(self, results: list[dict]) -> str:
        """Generate a crawl report from results."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.REPORTS_DIR / f"report_{timestamp}.json"

        report = {
            "timestamp": timestamp,
            "total_spiders": len(results),
            "completed": sum(1 for r in results if r.get("status") == "completed"),
            "failed": sum(1 for r in results if r.get("status") in ("failed", "error")),
            "total_duration": sum(r.get("duration", 0) for r in results),
            "results": results,
        }

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Report saved: {report_file}")
        return str(report_file)

    def _load_state(self, path: Path) -> dict:
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _save_state(self, path: Path, state: dict):
        with open(path, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def resume_interrupted(self) -> list[str]:
        """Find and return list of spiders that were interrupted."""
        interrupted = []
        for state_file in self.STATE_DIR.glob("*.json"):
            state = self._load_state(state_file)
            if state.get("status") == "running":
                interrupted.append(state_file.stem)
        return interrupted
