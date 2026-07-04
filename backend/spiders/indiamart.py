"""
BuyerHunter AI — IndiaMART Spider

Crawls dir.indiamart.com category pages using Playwright for JS rendering.
Extracts company data from product listing cards.

Usage:
    python -m scrapy crawl indiamart -a queries='["palm oil"]' -a max_pages=2
"""

import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy

logger = logging.getLogger(__name__)


# Product keyword to IndiaMART category URL mapping
CATEGORY_MAP = {
    "palm oil": "palm-oil",
    "rbd palm olein": "rbd-palmolein-oil",
    "cp10": "rbd-palmolein-oil",
    "cp8": "rbd-palmolein-oil",
    "sunflower oil": "sunflower-oil",
    "soybean oil": "soyabean-oil",
    "refined oil": "refined-oil",
    "vegetable oil": "vegetable-oil",
    "cooking oil": "cooking-oil",
    "edible oil": "edib-oil",
    "mustard oil": "mustard-oil",
    "groundnut oil": "groundnut-oil",
    "coconut oil": "coconut-oil",
    "rice bran oil": "rice-bran-oil",
    "palm stearin": "palm-stearin",
    "palm kernel oil": "palm-kernel-oil",
    "oleochemical": "oleochemical",
    "glycerine": "glycerine",
    "fatty acid": "fatty-acid",
    "detergent": "detergent",
    "animal feed": "animal-feed",
    "bakery products": "bakery-products",
    "snacks": "snacks",
    "cosmetics": "cosmetics",
    "vanaspati": "vanaspati-oil",
    "shortening": "shortening-oil",
    "bakery fat": "bakery-fat",
    "soap": "soap-and-detergent",
    "bakery": "bakery-products",
    "snack": "snacks",
    "cosmetic": "cosmetics",
    "chocolate": "chocolate",
    "food": "food-products",
}


class IndiaMARTSpider(scrapy.Spider):
    """Crawl IndiaMART category pages for product suppliers."""

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

    BASE_URL = "https://dir.indiamart.com/impcat"

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
        # Build start_urls from queries (works reliably on Windows)
        self.start_urls = []
        self._query_map = {}
        for query in self.queries:
            slug = self._query_to_slug(query)
            url = f"{self.BASE_URL}/{slug}.html"
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
            next_url = f"{self.BASE_URL}/{self._query_to_slug(query)}.html?pg={next_page}"
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
                            "h2, [class*='card']",
                            timeout=15000,
                        ),
                    ],
                },
                errback=self.handle_error,
                priority=10,
            )

    def _parse_html_cards(self, response, query):
        """Parse company data from template7 seller info cards."""
        seller_cards = response.css(".template7-seller-info")
        if not seller_cards:
            seller_cards = response.css("[class*='seller-info']")

        seen_companies = set()
        for card in seller_cards:
            # Get seller name from the card
            name_el = card.css(".wlc1 a::text, a::text").get()
            if not name_el:
                name_el = card.css("::text").get()
            if not name_el:
                continue

            company_name = name_el.strip()
            if not company_name or len(company_name) < 3 or company_name in seen_companies:
                continue
            seen_companies.add(company_name)

            # Get location and years from seller row
            row_text = card.css(".template7-seller-row ::text").getall()
            full_text = " ".join(t.strip() for t in row_text if t.strip())

            # Parse location and years
            location = ""
            years = ""
            loc_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:,\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)*)\s*·\s*(\d+\s*(?:yrs?|Months?|yr))', full_text)
            if loc_match:
                location = loc_match.group(1).strip()
                years = loc_match.group(2).strip()
            else:
                # Try simpler pattern
                parts = full_text.split("·")
                if len(parts) >= 2:
                    location = parts[0].strip().split(company_name)[-1].strip()
                    years = parts[1].strip()

            parsed_city, parsed_state = self._parse_location(location)

            # Get product name from the parent card (template7-card-meta)
            parent = card.xpath("..")
            product = parent.css("h2::text").get() or ""
            product = product.strip()

            # Get price
            price = parent.css("[class*='price'] ::text, .prc ::text").get() or ""
            price = price.strip()

            yield {
                "company_name": company_name,
                "website": None,
                "phone": None,
                "whatsapp": None,
                "email": None,
                "address": None,
                "city": parsed_city,
                "state": parsed_state,
                "country": "India",
                "gst_number": None,
                "industry": self._guess_industry(query),
                "products": json.dumps([product]) if product else None,
                "lead_score": 0,
                "source": "indiamart",
                "crawl_date": datetime.now(timezone.utc).isoformat(),
                "about_us": f"Product: {product}. Price: {price}. Years: {years}" if years else None,
            }

    def _parse_seller_text(self, text):
        """Parse company name, city, and years from seller text."""
        if not text:
            return None, None, None

        text = text.strip()
        # Pattern: "CompanyName City · X yrs" or "CompanyNameCity · X yrs"
        match = re.match(r'^(.+?)(?:\s{2,}|\n)(.+?)(?:\s*·\s*(\d+\s*(?:yrs?|Months?|yr)))?$', text)
        if match:
            return match.group(1).strip(), match.group(2).strip(), match.group(3)

        # Try without years
        parts = text.split("·")
        name_part = parts[0].strip()

        # Try to split name and city
        for sep in ["  ", "\t"]:
            if sep in name_part:
                parts2 = name_part.split(sep, 1)
                return parts2[0].strip(), parts2[1].strip(), parts[1].strip() if len(parts) > 1 else None

        return name_part, None, parts[1].strip() if len(parts) > 1 else None

    def _parse_location(self, text):
        """Parse city and state from location text."""
        if not text:
            return None, None

        text = re.sub(r'\s*·\s*\d+.*$', '', text).strip()
        parts = [p.strip() for p in text.split(",")]
        city = parts[0] if parts else None
        state = parts[-1] if len(parts) > 1 and len(parts[-1]) > 3 else None
        return city, state

    def _build_item(self, data, query):
        """Build a company item from extracted data."""
        name = data.get("seller", "").strip()
        if not name or len(name) < 3:
            return None

        location = data.get("location", "")
        city, state = self._parse_location(location)

        return {
            "company_name": name,
            "website": None,
            "phone": None,
            "whatsapp": None,
            "email": None,
            "address": None,
            "city": city,
            "state": state,
            "country": "India",
            "gst_number": None,
            "industry": self._guess_industry(query),
            "products": json.dumps([data.get("product", "")]),
            "lead_score": 0,
            "source": "indiamart",
            "crawl_date": datetime.now(timezone.utc).isoformat(),
        }

    def _query_to_slug(self, query):
        """Convert a search query to an IndiaMART category slug."""
        q = query.lower().strip()

        # Remove common suffixes
        clean = re.sub(r'\b(manufacturer|supplier|distributor|dealer|wholesaler|retailer|importer|exporter|company|companies|india|products?)\b', '', q).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()

        # Direct lookup
        if clean in CATEGORY_MAP:
            return CATEGORY_MAP[clean]
        if q in CATEGORY_MAP:
            return CATEGORY_MAP[q]

        # Partial match - check if any keyword matches
        best_match = None
        best_len = 0
        for keyword, slug in CATEGORY_MAP.items():
            if keyword in clean and len(keyword) > best_len:
                best_match = slug
                best_len = len(keyword)

        if best_match:
            return best_match

        # Default: slugify the query
        return re.sub(r'[^a-z0-9]+', '-', clean).strip('-')

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
