"""
BuyerHunter V2 — IndiaMART Crawler Adapter

India's largest B2B marketplace. Handles search, pagination,
and extraction of company listings.
"""

import re
import logging
from urllib.parse import quote_plus, urljoin

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawlResult, CrawledEntity

logger = logging.getLogger(__name__)


class IndiaMARTAdapter(BaseCrawlerAdapter):
    """
    Adapter for indiamart.com — India's largest B2B marketplace.
    Handles category slug mapping, search pagination, and card extraction.
    """

    @property
    def adapter_name(self) -> str:
        return "indiamart"

    @property
    def display_name(self) -> str:
        return "IndiaMART"

    @property
    def source_type(self) -> str:
        return "b2b_directory"

    @property
    def base_url(self) -> str:
        return "https://www.indiamart.com"

    @property
    def default_priority(self) -> int:
        return 10

    @property
    def rate_limit_seconds(self) -> float:
        return 2.0

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        Build IndiaMART search URLs with pagination.

        Pattern: https://www.indiamart.com/search.html?ss={query}&src=se&pn={page}
        """
        max_pages = kwargs.get("max_pages", self.max_pages_default)
        encoded = quote_plus(query)

        urls = []
        for page in range(1, max_pages + 1):
            url = (
                f"{self.base_url}/search.html"
                f"?ss={encoded}&src=se&pn={page}"
            )
            urls.append(url)

        return urls

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """
        Extract individual company listing URLs from search result pages.

        IndiaMART listings follow patterns like:
          /mp/{company_slug}/...
          /company/{company_id}/...
        """
        entity_urls: list[str] = []

        for search_url in search_result_urls:
            # In production, this fetches the page and parses links.
            # For now, we construct likely company URLs from search patterns.
            # The actual HTTP fetching happens in crawl().
            entity_urls.append(search_url)

        return entity_urls

    async def crawl(self, entity_urls: list[str], **kwargs) -> list[dict]:
        """
        Fetch raw HTML from IndiaMART pages.

        In production, uses httpx/playwright with rate limiting,
        proxy rotation, and anti-fingerprint headers.
        """
        import httpx

        pages: list[dict] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        async with httpx.AsyncClient(
            headers=headers, timeout=15, follow_redirects=True, verify=False,
        ) as client:
            for url in entity_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        pages.append({
                            "url": str(resp.url),
                            "html": resp.text,
                            "status_code": resp.status_code,
                        })
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {e}")

        return pages

    async def extract(self, raw_pages: list[dict], **kwargs) -> list[dict]:
        """
        Parse IndiaMART search result cards into structured data.

        Extracts: company name, website, phone, email, location,
        industry, products from listing cards.
        """
        from bs4 import BeautifulSoup

        records: list[dict] = []

        for page in raw_pages:
            html = page.get("html", "")
            url = page.get("url", "")
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")

            # IndiaMART search results use various card selectors
            cards = (
                soup.select("div.lst-pg")           # listing page cards
                or soup.select("div.product-card")   # product cards
                or soup.select("div.card")            # generic cards
            )

            for card in cards:
                record: dict = {"source_url": url}

                # Company name
                name_el = card.select_one("a.company-name, h2 a, h3 a, div.name a")
                if name_el:
                    record["company_name"] = name_el.get_text(strip=True)
                    record["company_url"] = urljoin(url, name_el.get("href", ""))

                # Website link
                website_el = card.select_one("a.website-link, a[href*='http']")
                if website_el:
                    record["website"] = website_el.get("href", "")

                # Phone
                phone_el = card.select_one("a[href^='tel:']")
                if phone_el:
                    record["phone"] = phone_el.get("href", "").replace("tel:", "")

                # Location
                loc_el = card.select_one("div.location, span.location, div.addr")
                if loc_el:
                    record["location"] = loc_el.get_text(strip=True)

                # Products / description
                desc_el = card.select_one("div.description, p.desc")
                if desc_el:
                    record["description"] = desc_el.get_text(strip=True)

                if record.get("company_name"):
                    records.append(record)

        return records

    async def normalize(self, raw_data: list[dict], **kwargs) -> list[CrawledEntity]:
        """Map IndiaMART records to canonical CrawledEntity."""
        entities: list[CrawledEntity] = []

        for record in raw_data:
            name = record.get("company_name", "").strip()
            if not name:
                continue

            # Parse location
            location = record.get("location", "")
            city, state = self._parse_location(location)

            # Extract business type from description
            desc = record.get("description", "").lower()
            is_manufacturer = any(kw in desc for kw in ["manufactur", "factory", "plant", "mill"])
            is_exporter = any(kw in desc for kw in ["export", "overseas"])
            is_importer = any(kw in desc for kw in ["import", "overseas buyer"])

            phone = self._normalize_phone(record.get("phone", ""))

            entity = CrawledEntity(
                canonical_name=name,
                website_url=record.get("website", "") or record.get("company_url", ""),
                phones=[phone] if phone else [],
                industry=record.get("industry", ""),
                is_manufacturer=is_manufacturer,
                is_importer=is_importer,
                is_exporter=is_exporter,
                hq_state=state,
                hq_city=city,
                description=record.get("description", ""),
                source=self.adapter_name,
                source_url=record.get("source_url", ""),
            )
            entities.append(entity)

        return entities

    def _parse_location(self, location: str) -> tuple[str, str]:
        """Parse 'City, State' or 'City, State, India' into (city, state)."""
        if not location:
            return "", ""
        parts = [p.strip() for p in location.split(",")]
        city = parts[0] if parts else ""
        state = parts[1] if len(parts) > 1 else ""
        if state.lower() in ("india", "in"):
            state = parts[1] if len(parts) > 2 else ""
        return city, state
