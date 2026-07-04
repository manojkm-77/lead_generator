"""
BuyerHunter AI — Direct Search Engine

Uses httpx to search business directories directly, bypassing Scrapy.
Falls back to IndiaMART's internal API for search results.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class DirectSearch:
    """Search business directories using httpx."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            },
        )

    async def search_indiamart(self, query: str, max_results: int = 20) -> list[dict]:
        """Search IndiaMART using their internal API."""
        companies = []

        try:
            # IndiaMART has an internal search API
            api_url = f"https://www.indiamart.com/api/search/get?ss={quote_plus(query)}&pgnum=1"

            resp = await self.client.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                if "response" in data and "data" in data["response"]:
                    for item in data["response"]["data"][:max_results]:
                        company = self._parse_indiamart_api_item(item, query)
                        if company:
                            companies.append(company)
        except Exception as e:
            logger.debug(f"IndiaMART API search failed: {e}")

        # Fallback: scrape search page
        if not companies:
            try:
                companies = await self._scrape_indiamart_search(query, max_results)
            except Exception as e:
                logger.debug(f"IndiaMART scrape failed: {e}")

        return companies

    async def _scrape_indiamart_search(self, query: str, max_results: int = 20) -> list[dict]:
        """Scrape IndiaMART search page for company listings."""
        companies = []
        url = f"https://www.indiamart.com/search.html?ss={quote_plus(query)}"

        resp = await self.client.get(url)
        if resp.status_code != 200:
            return companies

        # Try to find JSON data embedded in the page
        text = resp.text
        json_patterns = [
            r'window\.__NEXT_DATA__\s*=\s*({.*?});',
            r'var\s+searchData\s*=\s*({.*?});',
            r'"searchResults"\s*:\s*(\[.*?\])',
        ]

        for pattern in json_patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    companies.extend(self._parse_json_data(data, query))
                    if companies:
                        break
                except json.JSONDecodeError:
                    continue

        return companies[:max_results]

    def _parse_indiamart_api_item(self, item: dict, query: str) -> dict | None:
        """Parse IndiaMART API response item."""
        name = item.get("company_name") or item.get("name")
        if not name:
            return None

        return {
            "company_name": name.strip(),
            "website": item.get("website"),
            "phone": item.get("phone") or item.get("mobile"),
            "whatsapp": item.get("whatsapp"),
            "email": item.get("email"),
            "address": item.get("address"),
            "city": item.get("city"),
            "state": item.get("state"),
            "country": "India",
            "industry": self._guess_industry(query),
            "products": json.dumps(item.get("products", [])[:5]) if item.get("products") else None,
            "lead_score": 0,
            "source": "indiamart",
            "crawl_date": datetime.now(timezone.utc).isoformat(),
        }

    def _parse_json_data(self, data: dict | list, query: str) -> list[dict]:
        """Parse embedded JSON data from search page."""
        companies = []
        items = data if isinstance(data, list) else data.get("results", data.get("items", []))

        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    company = self._parse_indiamart_api_item(item, query)
                    if company:
                        companies.append(company)

        return companies

    def _guess_industry(self, query: str) -> str:
        """Guess industry from search query."""
        q = query.lower()
        if any(w in q for w in ["bakery", "snack", "namkeen"]):
            return "Bakery"
        if any(w in q for w in ["hotel", "restaurant", "catering"]):
            return "Hotel"
        if any(w in q for w in ["wholesale", "wholesaler", "dealer"]):
            return "Wholesaler"
        if any(w in q for w in ["distributor", "distribution"]):
            return "Distributor"
        if any(w in q for w in ["manufacturer", "factory", "production"]):
            return "Food Manufacturer"
        if any(w in q for w in ["import", "export", "trading"]):
            return "Importer/Exporter"
        if any(w in q for w in ["palm oil", "edible oil", "cooking oil", "vegetable oil"]):
            return "Edible Oil Trader"
        return "Food Processing Company"

    async def close(self):
        await self.client.aclose()
