import re
import json
import logging
from datetime import datetime, timezone

import scrapy

logger = logging.getLogger(__name__)


class BaseSpider(scrapy.Spider):
    """Base spider with standardized output, stats tracking, and common utilities."""

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504],
        "HTTPCACHE_ENABLED": True,
        "HTTPCACHE_EXPIRATION_SECS": 3600,
        "HTTPCACHE_DIR": ".httpcache",
    }

    # Subclasses override these
    SOURCE_NAME = "unknown"
    INDUSTRY_HINT = None

    def __init__(self, queries=None, keywords=None, max_pages=5, urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(queries, str):
            try:
                parsed = json.loads(queries)
                self.queries = parsed if isinstance(parsed, list) else [parsed]
            except (json.JSONDecodeError, TypeError):
                self.queries = [queries]
        else:
            self.queries = queries or keywords or []
        self.max_pages = int(max_pages)
        if isinstance(urls, str):
            try:
                parsed = json.loads(urls)
                self.urls = parsed if isinstance(parsed, list) else [parsed]
            except (json.JSONDecodeError, TypeError):
                self.urls = [urls]
        else:
            self.urls = urls or []
        self.stats = {
            "pages_crawled": 0,
            "companies_found": 0,
            "duplicates": 0,
            "errors": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
        }

    async def start(self):
        for r in self.start_requests():
            yield r

    def start_requests(self):
        raise NotImplementedError("Subclasses must implement start_requests")

    def make_item(self, **kwargs):
        """Create a standardized CompanyItem with defaults."""
        from backend.spiders.items import CompanyItem
        item = CompanyItem()
        defaults = {
            "source": self.SOURCE_NAME or self.name,
            "crawl_date": datetime.now(timezone.utc).isoformat(),
            "country": "India",
            "lead_score": 0,
        }
        for key, value in defaults.items():
            item[key] = value
        for key, value in kwargs.items():
            item[key] = value
        self.stats["companies_found"] += 1
        return item

    def extract_phones(self, response, selector="a[href^='tel:']::attr(href)"):
        """Extract and normalize phone numbers from response."""
        raw_phones = response.css(selector).getall()
        phones = []
        for raw in raw_phones:
            cleaned = raw.replace("tel:", "").strip()
            digits = re.sub(r"[^\d+]", "", cleaned)
            if len(digits) >= 10:
                phones.append(digits)
        return phones

    def extract_emails(self, response, selector="a[href^='mailto:']::attr(href)"):
        """Extract emails from response."""
        raw_emails = response.css(selector).getall()
        emails = []
        for raw in raw_emails:
            email = raw.replace("mailto:", "").strip().lower()
            if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
                emails.append(email)
        return emails

    def extract_website(self, response):
        """Extract external website link (not the source domain)."""
        links = response.css("a[href^='http']::attr(href)").getall()
        for link in links:
            domain = re.sub(r"https?://([^/]+).*", r"\1", link)
            allowed = [d for d in self.allowed_domains if d not in domain]
            if allowed and self.SOURCE_NAME.split("_")[0] not in domain:
                return link.rstrip("/")
        return None

    def extract_location(self, text):
        """Parse city and state from a location string."""
        if not text:
            return None, None
        text = re.sub(r"\s+", " ", text.strip())
        parts = [p.strip() for p in text.split(",")]
        city = parts[0].title() if parts else None
        state = parts[-1].title() if len(parts) > 1 else None
        if state and len(state) < 3:
            state = None
        return city, state

    def clean_text(self, text):
        """Clean and normalize text."""
        if not text:
            return None
        text = re.sub(r"\s+", " ", text.strip())
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        return text if text else None

    def handle_error(self, failure):
        """Default error handler."""
        self.stats["errors"].append(str(failure.value))
        self.logger.error(f"[{self.name}] Request failed: {failure.value}")

    def closed(self, reason):
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        self.stats["close_reason"] = reason
        self.logger.info(
            f"[{self.name}] Closed: reason={reason}, "
            f"pages={self.stats['pages_crawled']}, "
            f"companies={self.stats['companies_found']}, "
            f"duplicates={self.stats['duplicates']}"
        )
