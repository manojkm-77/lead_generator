"""
BuyerHunter V2 — Justdial Crawler Adapter

Local business directory. Strong for retail, wholesale, and service businesses.
City-specific search pattern.
"""

import logging
from urllib.parse import quote_plus, urljoin

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawledEntity

logger = logging.getLogger(__name__)


class JustdialAdapter(BaseCrawlerAdapter):
    """
    Adapter for justdial.com — India's leading local business directory.
    Excels at finding retail, wholesale, and service businesses by city.
    """

    @property
    def adapter_name(self) -> str:
        return "justdial"

    @property
    def display_name(self) -> str:
        return "Justdial"

    @property
    def source_type(self) -> str:
        return "local_directory"

    @property
    def base_url(self) -> str:
        return "https://www.justdial.com"

    @property
    def default_priority(self) -> int:
        return 9

    @property
    def rate_limit_seconds(self) -> float:
        return 3.0

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        Justdial requires city in URL path:
          https://www.justdial.com/{city}/{query}
        """
        city = kwargs.get("city", "India")
        max_pages = kwargs.get("max_pages", 3)
        encoded = quote_plus(query)

        urls = [f"{self.base_url}/{quote_plus(city)}/{encoded}"]

        # Justdial pagination uses page number suffix
        for page in range(2, max_pages + 1):
            urls.append(f"{self.base_url}/{quote_plus(city)}/{encoded}/page-{page}")

        return urls

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
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

            # Justdial listing cards
            cards = (
                soup.select("div.resultbox")
                or soup.select("div.store-details")
                or soup.select("li.resultbox")
            )

            for card in cards:
                record: dict = {"source_url": url}

                name_el = card.select_one("span.resultbox_title, h2 span, a.store-name")
                if name_el:
                    record["company_name"] = name_el.get_text(strip=True)

                # Justdial often obfuscates phone numbers
                phone_el = card.select_one("span.mobile_val, a[href^='tel:']")
                if phone_el:
                    raw_phone = phone_el.get_text(strip=True)
                    if phone_el.get("href", "").startswith("tel:"):
                        raw_phone = phone_el["href"].replace("tel:", "")
                    record["phone"] = raw_phone

                loc_el = card.select_one("span.resultbox_address, div.address")
                if loc_el:
                    record["location"] = loc_el.get_text(strip=True)

                rating_el = card.select_one("span.rating_star, span.resultbox_rating")
                if rating_el:
                    try:
                        record["rating"] = float(rating_el.get_text(strip=True))
                    except (ValueError, TypeError):
                        pass

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

            phone = self._normalize_phone(record.get("phone", ""))

            entities.append(CrawledEntity(
                canonical_name=name,
                phones=[phone] if phone else [],
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
        return city, state
