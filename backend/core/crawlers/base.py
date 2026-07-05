"""
BuyerHunter V2 — Abstract Crawler Adapter

Strict ABC defining the lifecycle contract every crawler source must implement:
  1. search()         — Generate search URLs for a query
  2. discover_urls()  — Extract candidate URLs from search results
  3. crawl()          — Fetch individual pages
  4. extract()        — Parse structured data from HTML
  5. normalize()      — Map raw data to canonical CrawledEntity schema

Adapters are stateless per-call. Shared HTTP clients and rate limiters
are injected at construction time.
"""

import abc
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Canonical output schema ─────────────────────────────────────────────────

class EntityType(str, Enum):
    COMPANY = "company"
    CONTACT = "contact"


@dataclass
class CrawledEntity:
    """
    Normalized output from any crawler adapter.
    Every adapter must produce this schema regardless of source.
    """
    entity_type: EntityType = EntityType.COMPANY

    # Core identity
    canonical_name: str = ""
    website_url: str = ""

    # Contact channels
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    whatsapp_numbers: list[str] = field(default_factory=list)
    linkedin_urls: list[str] = field(default_factory=list)

    # Classification
    industry: str = ""
    sub_industry: str = ""
    is_manufacturer: bool = False
    is_importer: bool = False
    is_exporter: bool = False
    is_distributor: bool = False
    is_wholesaler: bool = False
    is_retailer: bool = False

    # Legal identifiers
    gst_number: str = ""
    cin_number: str = ""
    iec_code: str = ""
    fssai_number: str = ""

    # Location
    hq_country: str = "IN"
    hq_state: str = ""
    hq_city: str = ""
    hq_district: str = ""
    hq_pincode: str = ""
    hq_address: str = ""
    factory_address: str = ""
    warehouse_address: str = ""

    # Geolocation
    latitude: float | None = None
    longitude: float | None = None

    # Company details
    legal_name: str = ""
    description: str = ""
    employee_count: int | None = None
    founded_year: int | None = None
    google_rating: float | None = None

    # Products / brands
    products: list[str] = field(default_factory=list)
    brands: list[str] = field(default_factory=list)

    # Contact person (for contact-type entities)
    person_name: str = ""
    designation: str = ""
    department: str = ""

    # Provenance
    source: str = ""
    source_url: str = ""
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def fingerprint(self) -> str:
        """Deterministic dedup fingerprint based on name + location."""
        key = f"{self.canonical_name.lower().strip()}|{self.hq_state.lower()}|{self.hq_city.lower()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


@dataclass
class CrawlResult:
    """Standard result from any crawler adapter execution."""
    entities: list[CrawledEntity] = field(default_factory=list)
    pages_crawled: int = 0
    urls_discovered: int = 0
    urls_visited: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_time_seconds: float = 0.0
    success: bool = True
    adapter_name: str = ""


# ── Abstract Base Class ──────────────────────────────────────────────────────

class BaseCrawlerAdapter(abc.ABC):
    """
    Strict interface every crawler adapter must implement.

    Lifecycle (called in order by the orchestrator):
      1. search(query)         → list of search result URLs
      2. discover_urls(results) → list of entity page URLs
      3. crawl(urls)           → raw HTML pages
      4. extract(pages)        → raw parsed data
      5. normalize(raw_data)   → list of CrawledEntity

    The orchestrator calls these in sequence. Adapters may override
    the default pipeline via execute() for sources that need custom flows.
    """

    # ── Subclass metadata (must override) ────────────────────────────────────

    @property
    @abc.abstractmethod
    def adapter_name(self) -> str:
        """Unique adapter identifier (e.g., 'indiamart', 'justdial')."""

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """Human-readable source name (e.g., 'IndiaMART')."""

    @property
    @abc.abstractmethod
    def source_type(self) -> str:
        """Category: b2b_directory, local_directory, government_registry, corporate_website."""

    @property
    @abc.abstractmethod
    def base_url(self) -> str:
        """Root URL for this source."""

    @property
    def default_priority(self) -> int:
        """Default priority 1-10 (10 = highest). Override per adapter."""
        return 5

    @property
    def rate_limit_seconds(self) -> float:
        """Minimum seconds between requests. Override per adapter."""
        return 2.0

    @property
    def max_pages_default(self) -> int:
        """Default max pages to crawl per search."""
        return 5

    # ── Lifecycle hooks ──────────────────────────────────────────────────────

    @abc.abstractmethod
    async def search(self, query: str, **kwargs) -> list[str]:
        """
        Generate search result page URLs for a query.

        Args:
            query: The search query string
            **kwargs: Source-specific options (city, state, page, etc.)

        Returns:
            List of search result page URLs to process
        """

    @abc.abstractmethod
    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """
        Extract individual entity/company page URLs from search result pages.

        Args:
            search_result_urls: URLs from search()
            **kwargs: Source-specific options

        Returns:
            List of entity page URLs to crawl
        """

    @abc.abstractmethod
    async def crawl(self, entity_urls: list[str], **kwargs) -> list[dict]:
        """
        Fetch raw HTML/content from entity page URLs.

        Args:
            entity_urls: URLs from discover_urls()
            **kwargs: Source-specific options (headers, proxy, etc.)

        Returns:
            List of dicts with 'url', 'html', 'status_code' keys
        """

    @abc.abstractmethod
    async def extract(self, raw_pages: list[dict], **kwargs) -> list[dict]:
        """
        Parse structured data from raw HTML pages.

        Args:
            raw_pages: Output from crawl()
            **kwargs: Source-specific options

        Returns:
            List of raw parsed data dicts
        """

    @abc.abstractmethod
    async def normalize(self, raw_data: list[dict], **kwargs) -> list[CrawledEntity]:
        """
        Map raw parsed data to canonical CrawledEntity schema.

        Args:
            raw_data: Output from extract()
            **kwargs: Source-specific options

        Returns:
            List of normalized CrawledEntity objects
        """

    # ── Default pipeline ─────────────────────────────────────────────────────

    async def execute(self, query: str, **kwargs) -> CrawlResult:
        """
        Execute the full crawl pipeline: search → discover → crawl → extract → normalize.

        Override this method for sources that need a custom flow.
        """
        import time
        start = time.monotonic()
        result = CrawlResult(adapter_name=self.adapter_name)

        try:
            # Step 1: Search
            search_urls = await self.search(query, **kwargs)
            logger.debug(f"[{self.adapter_name}] search → {len(search_urls)} URLs")

            # Step 2: Discover entity URLs
            entity_urls = await self.discover_urls(search_urls, **kwargs)
            result.urls_discovered = len(entity_urls)
            logger.debug(f"[{self.adapter_name}] discover → {len(entity_urls)} entity URLs")

            max_pages = kwargs.get("max_pages", self.max_pages_default)
            entity_urls = entity_urls[:max_pages * 10]  # Cap entity URLs

            # Step 3: Crawl
            raw_pages = await self.crawl(entity_urls, **kwargs)
            result.pages_crawled = len(raw_pages)
            result.urls_visited = [p.get("url", "") for p in raw_pages]
            logger.debug(f"[{self.adapter_name}] crawl → {len(raw_pages)} pages")

            # Step 4: Extract
            raw_data = await self.extract(raw_pages, **kwargs)
            logger.debug(f"[{self.adapter_name}] extract → {len(raw_data)} records")

            # Step 5: Normalize
            entities = await self.normalize(raw_data, **kwargs)
            result.entities = entities
            logger.debug(f"[{self.adapter_name}] normalize → {len(entities)} entities")

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            logger.error(f"[{self.adapter_name}] pipeline failed: {e}")

        result.execution_time_seconds = time.monotonic() - start
        return result

    # ── Shared utilities ─────────────────────────────────────────────────────

    def _normalize_phone(self, raw: str) -> str:
        """Normalize Indian phone number to 10-digit format."""
        import re
        digits = re.sub(r"[^\d]", "", raw)
        if digits.startswith("91") and len(digits) > 10:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) > 10:
            digits = digits[1:]
        return digits if len(digits) == 10 else ""

    def _normalize_email(self, raw: str) -> str:
        """Lowercase and validate email format."""
        import re
        email = raw.strip().lower()
        if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
            return email
        return ""

    def _normalize_gst(self, raw: str) -> str:
        """Normalize GST number to uppercase, 15-char format."""
        import re
        gst = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        return gst if len(gst) == 15 else ""
