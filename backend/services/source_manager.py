"""
BuyerHunter AI — Source Manager (Plug-and-Play Crawler Adapters)

Every adapter returns the SAME schema regardless of source.
Add new sources by implementing the CrawlerAdapter interface.
"""

import abc
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, asdict, field
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Unified Data Schema — ALL adapters return this
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DiscoveredCompany:
    company_name: str
    website: str = ""
    phone: str = ""
    email: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = "India"
    pincode: str = ""
    district: str = ""
    gst_number: str = ""
    industry: str = ""
    products: list = field(default_factory=list)
    brands: list = field(default_factory=list)
    description: str = ""
    source: str = ""
    source_url: str = ""
    is_manufacturer: bool = False
    is_importer: bool = False
    is_exporter: bool = False
    is_distributor: bool = False
    is_wholesaler: bool = False
    is_retailer: bool = False
    official_email: str = ""
    sales_email: str = ""
    procurement_email: str = ""
    support_email: str = ""
    official_phone: str = ""
    whatsapp_business: str = ""
    linkedin_url: str = ""
    google_maps_url: str = ""
    google_rating: float = 0.0
    certifications: list = field(default_factory=list)
    fssai_number: str = ""
    apeda_registration: str = ""
    iso_certification: str = ""
    iec_code: str = ""
    factory_address: str = ""
    warehouse_address: str = ""
    office_address: str = ""
    social_media: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["products"] = json.dumps(self.products) if self.products else ""
        d["brands"] = json.dumps(self.brands) if self.brands else ""
        d["certifications"] = json.dumps(self.certifications) if self.certifications else ""
        d["social_media"] = json.dumps(self.social_media) if self.social_media else ""
        return d


@dataclass
class DiscoveredContact:
    person_name: str = ""
    designation: str = ""
    department: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    confidence_score: int = 50
    source_url: str = ""
    source: str = ""


@dataclass
class CrawlResult:
    """Standard result from any crawler adapter."""
    companies: list[DiscoveredCompany] = field(default_factory=list)
    contacts: list[DiscoveredContact] = field(default_factory=list)
    pages_crawled: int = 0
    urls_visited: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    success: bool = True


# ═══════════════════════════════════════════════════════════════════════════════
# Abstract Adapter Interface
# ═══════════════════════════════════════════════════════════════════════════════

class CrawlerAdapter(abc.ABC):
    """Base class for all crawler adapters. Every source implements this."""

    @abc.abstractproperty
    def name(self) -> str:
        """Unique source name (e.g., 'indiamart', 'justdial')."""

    @abc.abstractproperty
    def display_name(self) -> str:
        """Human-readable name (e.g., 'IndiaMART')."""

    @abc.abstractproperty
    def source_type(self) -> str:
        """Type: 'b2b_directory', 'local_directory', 'trade_directory', 'web_search', 'government', 'association'."""

    @abc.abstractproperty
    def priority(self) -> int:
        """Default priority (1-10). Higher = better source."""

    @abc.abstractproperty
    def rate_limit(self) -> float:
        """Seconds to wait between requests."""

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        """
        Execute a discovery search against this source.
        Returns CrawlResult with discovered companies and contacts.
        """
        raise NotImplementedError

    async def verify(self, company: DiscoveredCompany) -> dict:
        """Verify company information against this source. Returns confidence details."""
        return {"verified": False, "confidence": 0, "details": {}}

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        """Get the search URL pattern for this source."""
        return ""

    def build_search_url(self, query: str, page: int = 1, city: str = "", **kwargs) -> str:
        """Build a search URL for this source."""
        return self.get_url_pattern(query, city, **kwargs)


# ═══════════════════════════════════════════════════════════════════════════════
# Source Registry
# ═══════════════════════════════════════════════════════════════════════════════

class SourceRegistry:
    """Registry of all available crawler adapters. Allows dynamic addition."""

    def __init__(self):
        self._adapters: dict[str, CrawlerAdapter] = {}
        self._register_builtins()

    def _register_builtins(self):
        """Register built-in adapter stubs. Each delegates to the Scrapy spider."""
        builtins = [
            IndiaMARTAdapter(),
            JustDialAdapter(),
            TradeIndiaAdapter(),
            YellowPagesAdapter(),
            ExportersIndiaAdapter(),
        ]
        for adapter in builtins:
            self._adapters[adapter.name] = adapter

    def register(self, adapter: CrawlerAdapter):
        """Register a new adapter dynamically."""
        self._adapters[adapter.name] = adapter
        logger.info(f"Registered source adapter: {adapter.name} ({adapter.display_name})")

    def get(self, name: str) -> Optional[CrawlerAdapter]:
        """Get an adapter by name."""
        return self._adapters.get(name)

    def get_all(self) -> dict[str, CrawlerAdapter]:
        """Get all registered adapters."""
        return dict(self._adapters)

    def get_enabled(self) -> dict[str, CrawlerAdapter]:
        """Get all enabled adapters."""
        return {k: v for k, v in self._adapters.items() if not getattr(v, 'disabled', False)}

    def get_by_type(self, source_type: str) -> dict[str, CrawlerAdapter]:
        """Get adapters by type."""
        return {k: v for k, v in self._adapters.items() if v.source_type == source_type}

    def get_summary(self) -> list[dict]:
        """Get summary of all registered sources."""
        return [
            {
                "name": a.name,
                "display_name": a.display_name,
                "type": a.source_type,
                "priority": a.priority,
                "enabled": not getattr(a, 'disabled', False),
            }
            for a in self._adapters.values()
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# Built-in Adapters (delegate to Scrapy spiders)
# ═══════════════════════════════════════════════════════════════════════════════

class IndiaMARTAdapter(CrawlerAdapter):
    name = "indiamart"
    display_name = "IndiaMART"
    source_type = "b2b_directory"
    priority = 10
    rate_limit = 2.0

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        return f"https://www.indiamart.com/search.html?ss={query}&src=se"

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        """Run the IndiaMART Scrapy spider for this query."""
        return await self._run_spider("indiamart", query, max_pages)


class JustDialAdapter(CrawlerAdapter):
    name = "justdial"
    display_name = "JustDial"
    source_type = "local_directory"
    priority = 9
    rate_limit = 3.0

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        if city:
            return f"https://www.justdial.com/{city}/{query}"
        return f"https://www.justdial.com/search?q={query}"

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        return await self._run_spider("justdial", query, max_pages)


class TradeIndiaAdapter(CrawlerAdapter):
    name = "tradeindia"
    display_name = "TradeIndia"
    source_type = "b2b_directory"
    priority = 8
    rate_limit = 2.0

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        return f"https://www.tradeindia.com/search.html?keyword={query}"

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        return await self._run_spider("tradeindia", query, max_pages)


class YellowPagesAdapter(CrawlerAdapter):
    name = "yellowpages"
    display_name = "Yellow Pages India"
    source_type = "local_directory"
    priority = 7
    rate_limit = 2.0

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        return f"https://www.yellowpages.in/search?search_text={query}"

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        return await self._run_spider("yellowpages", query, max_pages)


class ExportersIndiaAdapter(CrawlerAdapter):
    name = "exportersindia"
    display_name = "ExportersIndia"
    source_type = "trade_directory"
    priority = 8
    rate_limit = 2.0

    def get_url_pattern(self, query: str, city: str = "", **kwargs) -> str:
        return f"https://www.exportersindia.com/search.html?ss={query}"

    async def discover(self, query: str, max_pages: int = 3, **kwargs) -> CrawlResult:
        return await self._run_spider("exportersindia", query, max_pages)


# ═══════════════════════════════════════════════════════════════════════════════
# Spider Runner (delegates to Scrapy subprocess)
# ═══════════════════════════════════════════════════════════════════════════════

class SpiderRunner:
    """Runs Scrapy spiders as subprocesses and collects results."""

    SPIDER_MODULES = {
        "indiamart": "backend.spiders.indiamart",
        "justdial": "backend.spiders.justdial",
        "tradeindia": "backend.spiders.tradeindia",
        "yellowpages": "backend.spiders.yellowpages",
        "exportersindia": "backend.spiders.exportersindia",
    }

    @staticmethod
    async def run_spider(spider_name: str, query: str, max_pages: int = 3) -> CrawlResult:
        """Run a spider and collect results."""
        if spider_name not in SpiderRunner.SPIDER_MODULES:
            return CrawlResult(success=False, errors=[f"Unknown spider: {spider_name}"])

        import subprocess
        import sys
        import sqlite3
        from pathlib import Path

        start = time.time()
        cwd = str(Path(__file__).resolve().parent.parent.parent)
        db_path = str(Path(cwd) / "buyerhunter.db")

        cmd = [
            sys.executable, "-m", "scrapy", "crawl", spider_name,
            "-a", f"queries={json.dumps([query])}",
            "-a", f"max_pages={max_pages}",
            "-s", "LOG_LEVEL=WARNING",
        ]

        try:
            # Count companies before
            conn = sqlite3.connect(db_path)
            before = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            conn.close()

            # Run spider
            proc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd, capture_output=True, text=True, cwd=cwd, timeout=300,
                )
            )

            # Poll DB for new companies
            for _ in range(15):
                await asyncio.sleep(1)
                conn = sqlite3.connect(db_path)
                after = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
                conn.close()
                if after > before:
                    break

            new_count = max(0, after - before)

            # Collect new companies
            companies = []
            if new_count > 0:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM companies ORDER BY id DESC LIMIT ?", (new_count,)
                ).fetchall()
                conn.close()

                for r in rows:
                    row = dict(r)
                    discovered = DiscoveredCompany(
                        company_name=row.get("company_name", ""),
                        website=row.get("website", ""),
                        phone=row.get("phone", ""),
                        email=row.get("email", ""),
                        city=row.get("city", ""),
                        state=row.get("state", ""),
                        industry=row.get("industry", ""),
                        source=spider_name,
                        source_url=row.get("source_url", ""),
                        is_manufacturer=row.get("is_manufacturer", False),
                        is_importer=row.get("is_importer", False),
                        is_exporter=row.get("is_exporter", False),
                        is_distributor=row.get("is_distributor", False),
                        official_email=row.get("official_email", ""),
                        procurement_email=row.get("procurement_email", ""),
                        gst_number=row.get("gst_number", ""),
                        fssai_number=row.get("fssai_number", ""),
                        iec_code=row.get("iec_code", ""),
                        description=row.get("about_us", ""),
                    )
                    companies.append(discovered)

            elapsed = time.time() - start
            success = proc.returncode == 0

            logger.info(
                f"[SpiderRunner] {spider_name} '{query}': {new_count} companies in {elapsed:.1f}s"
            )

            return CrawlResult(
                companies=companies,
                pages_crawled=1,
                urls_visited=[query],
                errors=[] if success else [proc.stderr[-500:]],
                execution_time=elapsed,
                success=success,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            logger.warning(f"[SpiderRunner] {spider_name} '{query}' timed out after {elapsed:.1f}s")
            return CrawlResult(
                success=False,
                errors=["Timeout after 300s"],
                execution_time=elapsed,
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"[SpiderRunner] {spider_name} '{query}' failed: {e}")
            return CrawlResult(
                success=False,
                errors=[str(e)],
                execution_time=elapsed,
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Global Singleton
# ═══════════════════════════════════════════════════════════════════════════════

_source_registry: Optional[SourceRegistry] = None


def get_source_registry() -> SourceRegistry:
    """Get or create the global source registry singleton."""
    global _source_registry
    if _source_registry is None:
        _source_registry = SourceRegistry()
    return _source_registry
