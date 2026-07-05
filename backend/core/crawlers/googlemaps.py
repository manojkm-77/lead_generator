"""
BuyerHunter V2 — Google Maps Crawler Adapter

Business listings from Google Maps. Strong for location-verified
businesses with ratings, reviews, and contact info.
"""

import logging
from urllib.parse import quote_plus

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawledEntity

logger = logging.getLogger(__name__)


class GoogleMapsAdapter(BaseCrawlerAdapter):
    """
    Adapter for Google Maps business listings.
    Uses Places API or web scraping for business discovery.
    """

    @property
    def adapter_name(self) -> str:
        return "google_maps"

    @property
    def display_name(self) -> str:
        return "Google Maps"

    @property
    def source_type(self) -> str:
        return "local_directory"

    @property
    def base_url(self) -> str:
        return "https://www.google.com/maps"

    @property
    def default_priority(self) -> int:
        return 7

    @property
    def rate_limit_seconds(self) -> float:
        return 3.0

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        Google Maps search URL pattern:
          https://www.google.com/maps/search/{query}
        """
        city = kwargs.get("city", "")
        state = kwargs.get("state", "")

        search_term = query
        if city:
            search_term += f" {city}"
        if state:
            search_term += f" {state}"

        encoded = quote_plus(search_term)
        return [f"{self.base_url}/search/{encoded}"]

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """Google Maps results are in-page, not separate URLs."""
        return list(search_result_urls)

    async def crawl(self, entity_urls: list[str], **kwargs) -> list[dict]:
        """
        Fetch Google Maps search results pages.
        In production, this would use Playwright for JS rendering.
        """
        import httpx

        pages: list[dict] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
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
        Parse Google Maps business listings from HTML.
        Google Maps heavily uses JS, so in production this requires Playwright.
        """
        from bs4 import BeautifulSoup

        records: list[dict] = []

        for page in raw_pages:
            html = page.get("html", "")
            url = page.get("url", "")
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")

            # Google Maps result cards
            cards = soup.select("div.Nv2PK, div[jsaction]")

            for card in cards:
                record: dict = {"source_url": url}

                # Business name
                name_el = card.select_one("div.qBF1Pd, span.fontHeadlineSmall")
                if name_el:
                    record["company_name"] = name_el.get_text(strip=True)

                # Rating
                rating_el = card.select_one("span.MW4etd, span.ZkP5Je")
                if rating_el:
                    try:
                        record["rating"] = float(rating_el.get_text(strip=True))
                    except (ValueError, TypeError):
                        pass

                # Category/type
                category_el = card.select_one("span.W4Efsd:last-child")
                if category_el:
                    record["industry"] = category_el.get_text(strip=True)

                # Address snippet
                addr_el = card.select_one("span.W4Efsd span")
                if addr_el:
                    record["location"] = addr_el.get_text(strip=True)

                if record.get("company_name"):
                    records.append(record)

        return records

    async def normalize(self, raw_data: list[dict], **kwargs) -> list[CrawledEntity]:
        entities: list[CrawledEntity] = []

        for record in raw_data:
            name = record.get("company_name", "").strip()
            if not name:
                continue

            location = record.get("location", "")
            city, state = self._parse_location(location)

            entities.append(CrawledEntity(
                canonical_name=name,
                industry=record.get("industry", ""),
                hq_state=state,
                hq_city=city,
                google_rating=record.get("rating"),
                source=self.adapter_name,
                source_url=record.get("source_url", ""),
            ))

        return entities

    def _parse_location(self, location: str) -> tuple[str, str]:
        if not location:
            return "", ""
        parts = [p.strip() for p in location.split(",")]
        city = parts[0] if parts else ""
        state = parts[1] if len(parts) > 1 else ""
        return city, state
