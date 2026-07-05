"""
BuyerHunter V2 — FSSAI Registry Crawler Adapter

Government registry for food safety licenses.
High-confidence source for food businesses in India.
"""

import logging
from urllib.parse import quote_plus

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawledEntity

logger = logging.getLogger(__name__)


class FSSAIAdapter(BaseCrawlerAdapter):
    """
    Adapter for FSSAI (Food Safety and Standards Authority of India)
    license registry. Government source with high data confidence.
    """

    @property
    def adapter_name(self) -> str:
        return "fssai"

    @property
    def display_name(self) -> str:
        return "FSSAI Registry"

    @property
    def source_type(self) -> str:
        return "government_registry"

    @property
    def base_url(self) -> str:
        return "https://foodlicensing.fssai.gov.in"

    @property
    def default_priority(self) -> int:
        return 6

    @property
    def rate_limit_seconds(self) -> float:
        return 5.0  # Government site — be respectful

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        FSSAI license search URL pattern.
        Note: FSSAI portal may require API access or form submission.
        This constructs the search URL for the licensing portal.
        """
        state = kwargs.get("state", "")
        encoded = quote_plus(query)

        urls = [f"{self.base_url}/index.aspx#/search?keyword={encoded}"]

        if state:
            urls.append(f"{self.base_url}/index.aspx#/search?keyword={encoded}&state={quote_plus(state)}")

        return urls

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """FSSAI results are in-page table rows, not separate URLs."""
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
            headers=headers, timeout=20, follow_redirects=True, verify=False,
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
                    logger.debug(f"Failed to fetch FSSAI page: {e}")

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

            # FSSAI table rows
            rows = soup.select("table tbody tr, div.license-row")

            for row in rows:
                record: dict = {"source_url": url}

                cells = row.select("td")
                if len(cells) >= 3:
                    record["company_name"] = cells[0].get_text(strip=True)
                    record["fssai_number"] = cells[1].get_text(strip=True)
                    record["license_type"] = cells[2].get_text(strip=True)

                    if len(cells) >= 5:
                        record["state"] = cells[3].get_text(strip=True)
                        record["address"] = cells[4].get_text(strip=True)

                if record.get("company_name"):
                    records.append(record)

        return records

    async def normalize(self, raw_data: list[dict], **kwargs) -> list[CrawledEntity]:
        entities: list[CrawledEntity] = []

        for record in raw_data:
            name = record.get("company_name", "").strip()
            if not name:
                continue

            fssai = self._normalize_fssai(record.get("fssai_number", ""))

            entities.append(CrawledEntity(
                canonical_name=name,
                fssai_number=fssai,
                hq_state=record.get("state", ""),
                hq_address=record.get("address", ""),
                industry="food processing",
                source=self.adapter_name,
                source_url=record.get("source_url", ""),
            ))

        return entities

    def _normalize_fssai(self, raw: str) -> str:
        """Normalize FSSAI license number."""
        import re
        digits = re.sub(r"[^A-Za-z0-9]", "", raw)
        return digits if len(digits) >= 12 else ""
