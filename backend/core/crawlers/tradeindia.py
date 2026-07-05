"""
BuyerHunter V2 — TradeIndia Crawler Adapter

B2B trade directory focused on manufacturers and exporters.
"""

import logging
from urllib.parse import quote_plus, urljoin

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawledEntity

logger = logging.getLogger(__name__)


class TradeIndiaAdapter(BaseCrawlerAdapter):
    """
    Adapter for tradeindia.com — B2B trade directory
    strong in manufacturer and exporter listings.
    """

    @property
    def adapter_name(self) -> str:
        return "tradeindia"

    @property
    def display_name(self) -> str:
        return "TradeIndia"

    @property
    def source_type(self) -> str:
        return "b2b_directory"

    @property
    def base_url(self) -> str:
        return "https://www.tradeindia.com"

    @property
    def default_priority(self) -> int:
        return 8

    @property
    def rate_limit_seconds(self) -> float:
        return 2.0

    async def search(self, query: str, **kwargs) -> list[str]:
        max_pages = kwargs.get("max_pages", self.max_pages_default)
        encoded = quote_plus(query)

        return [
            f"{self.base_url}/search.html?keyword={encoded}&pn={page}"
            for page in range(1, max_pages + 1)
        ]

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """TradeIndia company profile URLs from search results."""
        return list(search_result_urls)

    async def crawl(self, entity_urls: list[str], **kwargs) -> list[dict]:
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
        from bs4 import BeautifulSoup

        records: list[dict] = []

        for page in raw_pages:
            html = page.get("html", "")
            url = page.get("url", "")
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")

            cards = (
                soup.select("div.company-box")
                or soup.select("div.search-result")
                or soup.select("div.card")
            )

            for card in cards:
                record: dict = {"source_url": url}

                name_el = card.select_one("a.company-name, h2 a, h3 a")
                if name_el:
                    record["company_name"] = name_el.get_text(strip=True)
                    record["company_url"] = urljoin(url, name_el.get("href", ""))

                phone_el = card.select_one("a[href^='tel:']")
                if phone_el:
                    record["phone"] = phone_el.get("href", "").replace("tel:", "")

                loc_el = card.select_one("div.location, span.location")
                if loc_el:
                    record["location"] = loc_el.get_text(strip=True)

                desc_el = card.select_one("div.description, p.desc")
                if desc_el:
                    record["description"] = desc_el.get_text(strip=True)

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

            desc = record.get("description", "").lower()
            is_manufacturer = any(kw in desc for kw in ["manufactur", "factory", "mill", "plant"])
            is_exporter = "export" in desc

            phone = self._normalize_phone(record.get("phone", ""))

            entities.append(CrawledEntity(
                canonical_name=name,
                website_url=record.get("website", "") or record.get("company_url", ""),
                phones=[phone] if phone else [],
                is_manufacturer=is_manufacturer,
                is_exporter=is_exporter,
                hq_state=state,
                hq_city=city,
                description=record.get("description", ""),
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
        if state.lower() in ("india", "in"):
            state = ""
        return city, state
