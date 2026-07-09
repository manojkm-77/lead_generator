"""
BuyerHunter AI — IndiaMART Spider

Crawls indiamart.com search results for product suppliers.
Uses the search URL (not impcat directory) for reliable results.

Usage:
    python -m scrapy crawl indiamart -a queries='["palm oil buyers"]' -a max_pages=2
"""

import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)


class IndiaMARTSpider(scrapy.Spider):
    """Crawl IndiaMART search results for product suppliers."""

    name = "indiamart"
    allowed_domains = ["indiamart.com", "dir.indiamart.com"]

    custom_settings = {
        "DOWNLOAD_DELAY": 3,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "ROBOTSTXT_OBEY": False,
        "RETRY_TIMES": 2,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "HTTPCACHE_ENABLED": False,
        "DOWNLOAD_TIMEOUT": 60,
        "LOG_LEVEL": "INFO",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "DOWNLOAD_HANDLERS": {
            "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
            "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
        },
        "PLAYWRIGHT_BROWSER_TYPE": "chromium",
        "PLAYWRIGHT_LAUNCH_OPTIONS": {
            "headless": True,
            "args": ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        },
        "PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT": 30000,
    }

    SEARCH_URL = "https://www.indiamart.com/search"

    def __init__(self, queries=None, max_pages=3, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if queries:
            if isinstance(queries, str):
                try:
                    parsed = json.loads(queries)
                    self.queries = parsed if isinstance(parsed, list) else [parsed]
                except (json.JSONDecodeError, TypeError):
                    self.queries = [queries]
            else:
                self.queries = queries
        else:
            self.queries = ["palm oil"]
        self.max_pages = int(max_pages)
        self.stats = {
            "pages_crawled": 0,
            "companies_found": 0,
            "companies_saved": 0,
            "duplicates": 0,
            "errors": [],
            "start_time": datetime.now(timezone.utc).isoformat(),
        }
        self.start_urls = []
        self._query_map = {}
        for query in self.queries:
            params = {"q": query, "page": 1}
            url = f"{self.SEARCH_URL}?{urlencode(params)}"
            self.start_urls.append(url)
            self._query_map[url] = query
            self.logger.info(f"[indiamart] Queued: '{query}' -> {url}")

    def start_requests(self):
        """Generate requests with Playwright meta for each URL."""
        for url in self.start_urls:
            query = self._query_map.get(url, "unknown")
            self.logger.info(f"[indiamart] Requesting: '{query}' -> {url}")
            yield scrapy.Request(
                url,
                callback=self.parse_category,
                meta={
                    "query": query,
                    "page": 1,
                    "playwright": True,
                    "playwright_page_methods": [
                        scrapy.Request.method(
                            "wait_for_selector",
                            "h2, [class*='card'], [class*='seller']",
                            timeout=15000,
                        ),
                    ],
                },
                errback=self.handle_error,
            )

    def parse(self, response):
        """Default parse for start_urls fallback."""
        query = self._query_map.get(response.url, "unknown")
        response.meta["query"] = query
        response.meta["page"] = 1
        yield from self.parse_category(response)

    def parse_category(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta.get("query", "unknown")
        page = response.meta.get("page", 1)

        self.logger.info(
            f"[indiamart] Page {page} for '{query}' - status={response.status}"
        )

        if self._is_blocked(response):
            self.logger.warning(f"[indiamart] Blocked on page {page}")
            self.stats["errors"].append(f"Block on page {page} for '{query}'")
            return

        # Extract companies using JavaScript evaluation
        companies_data = response.meta.get("playwright_page_result")
        if companies_data:
            for data in companies_data:
                item = self._build_item(data, query)
                if item:
                    self.stats["companies_found"] += 1
                    yield item
        else:
            # Fallback: parse from HTML directly
            count = 0
            for item in self._parse_html_cards(response, query):
                self.stats["companies_found"] += 1
                count += 1
                yield item
            self.logger.info(f"[indiamart] Extracted {count} companies from HTML")

        # Follow next page
        if page < self.max_pages:
            next_page = page + 1
            params = {"q": query, "page": next_page}
            next_url = f"{self.SEARCH_URL}?{urlencode(params)}"
            yield scrapy.Request(
                next_url,
                callback=self.parse_category,
                meta={
                    "query": query,
                    "page": next_page,
                    "playwright": True,
                    "playwright_page_methods": [
                        scrapy.Request.method(
                            "wait_for_selector",
                            ".srch-rslt-itm, [class*='card'], [class*='seller']",
                            timeout=15000,
                        ),
                    ],
                },
                errback=self.handle_error,
                priority=10,
            )

    def _parse_html_cards(self, response, query):
        """Parse company data from IndiaMART search result cards."""
        seller_cards = response.css(".srch-rslt-itm, [class*='seller-info'], [class*='card']")
        seen_companies = set()
        for card in seller_cards:
            name_el = card.css("h2::text, [class*='name'] a::text, a[href*='supplier']::text").get()
            if not name_el:
                name_el = card.css("[class*='title']::text").get()
            if not name_el:
                continue
            company_name = name_el.strip()
            if not company_name or len(company_name) < 3 or company_name in seen_companies:
                continue
            seen_companies.add(company_name)
            location_text = card.css("[class*='loc']::text, span[class*='city']::text, [class*='address']::text").get()
            location = location_text.strip() if location_text else None
            city, state = self._parse_location(location)
            product = card.css("h2::text, [class*='product']::text").get()
            product = product.strip() if product else ""
            yield {
                "company_name": company_name,
                "website": None, "phone": None, "whatsapp": None, "email": None,
                "address": None, "city": city, "state": state, "country": "India",
                "gst_number": None, "industry": self._guess_industry(query),
                "products": json.dumps([product]) if product else None,
                "lead_score": 0, "source": "indiamart",
                "crawl_date": datetime.now(timezone.utc).isoformat(),
            }

    def _parse_location(self, text):
        if not text:
            return None, None
        parts = [p.strip() for p in text.split(",")]
        city = parts[0] if parts else None
        state = parts[-1] if len(parts) > 1 and len(parts[-1]) > 3 else None
        return city, state

    def _build_item(self, data, query):
        name = data.get("seller", "").strip()
        if not name or len(name) < 3:
            return None
        location = data.get("location", "")
        city, state = self._parse_location(location)
        return {
            "company_name": name, "website": None, "phone": None,
            "whatsapp": None, "email": None, "address": None,
            "city": city, "state": state, "country": "India",
            "gst_number": None, "industry": self._guess_industry(query),
            "products": json.dumps([data.get("product", "")]),
            "lead_score": 0, "source": "indiamart",
            "crawl_date": datetime.now(timezone.utc).isoformat(),
        }

    def _guess_industry(self, query):
        q = query.lower()
        if any(w in q for w in ["bakery", "snack", "namkeen"]):
            return "Bakery"
        if any(w in q for w in ["hotel", "restaurant", "catering"]):
            return "Hotel"
        if any(w in q for w in ["distributor", "distribution"]):
            return "Distributor"
        if any(w in q for w in ["manufacturer", "factory", "production"]):
            return "Food Manufacturer"
        if any(w in q for w in ["import", "export", "trading"]):
            return "Importer/Exporter"
        if any(w in q for w in ["palm oil", "edible oil", "cooking oil", "vegetable oil"]):
            return "Edible Oil Trader"
        return "Food Processing Company"

    def _is_blocked(self, response):
        text = response.text.lower() if hasattr(response, 'text') else ""
        return any(w in text for w in ["captcha", "verify you are human", "access denied"])

    def handle_error(self, failure):
        error_msg = str(failure.value)
        self.stats["errors"].append(error_msg)
        self.logger.error(f"[indiamart] Request failed: {error_msg}")

    def closed(self, reason):
        self.stats["end_time"] = datetime.now(timezone.utc).isoformat()
        self.stats["close_reason"] = reason
        self.logger.info("=" * 60)
        self.logger.info(f"[indiamart] CRAWL COMPLETE")
        self.logger.info(f"  Pages:    {self.stats['pages_crawled']}")
        self.logger.info(f"  Found:    {self.stats['companies_found']}")
        self.logger.info(f"  Errors:   {len(self.stats['errors'])}")
        self.logger.info(f"  Reason:   {reason}")
        self.logger.info("=" * 60)
