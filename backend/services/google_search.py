"""
BuyerHunter AI — Google Search Engine

Uses Google search to find company listings from business directories.
Extracts company data from search result snippets.
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


class GoogleSearch:
    """Search for companies via Google."""

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

    async def search(self, query: str, max_results: int = 20) -> list[dict]:
        """Search Google for companies matching the query."""
        companies = []

        # Add site-specific queries to target business directories
        search_queries = [
            f"{query} site:indiamart.com",
            f"{query} site:tradeindia.com",
            f"{query} site:exportersindia.com",
        ]

        for sq in search_queries:
            try:
                results = await self._google_search(sq, max_per_query=max_results // 3)
                companies.extend(results)
                await asyncio.sleep(2)  # Rate limit
            except Exception as e:
                logger.debug(f"Google search failed for '{sq}': {e}")

        # Deduplicate by company name
        seen = set()
        unique = []
        for c in companies:
            key = c.get("company_name", "").lower().strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(c)

        return unique[:max_results]

    async def _google_search(self, query: str, max_per_query: int = 10) -> list[dict]:
        """Perform a Google search and extract company data."""
        companies = []
        url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_per_query}"

        resp = await self.client.get(url)
        if resp.status_code != 200:
            return companies

        text = resp.text

        # Extract search result blocks
        # Google wraps results in divs with specific patterns
        results = re.findall(
            r'<a href="/url\?q=(https?://[^"&]+).*?<h3[^>]*>(.*?)</h3>.*?(?:<span[^>]*>(.*?)</span>)?',
            text,
            re.DOTALL,
        )

        for url_match, title, snippet in results:
            if not url_match or "google.com" in url_match:
                continue

            company = self._extract_company_from_result(url_match, title, snippet)
            if company:
                companies.append(company)

        # Also try to find company data from IndiaMART links
        indiamart_companies = self._extract_indiamart_from_html(text)
        companies.extend(indiamart_companies)

        return companies[:max_per_query]

    def _extract_company_from_result(self, url: str, title: str, snippet: str) -> dict | None:
        """Extract company info from a search result."""
        # Clean HTML tags
        title = re.sub(r'<[^>]+>', '', title).strip()
        snippet = re.sub(r'<[^>]+>', '', snippet or '').strip()

        if not title or len(title) < 3:
            return None

        # Try to extract location from snippet
        city = None
        state = None
        location_match = re.search(
            r'(?:in|from|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            snippet
        )
        if location_match:
            city = location_match.group(1)

        # Check for state names
        states = [
            "Maharashtra", "Gujarat", "Karnataka", "Tamil Nadu", "Delhi",
            "Kerala", "Andhra Pradesh", "Telangana", "West Bengal", "Rajasthan",
            "Uttar Pradesh", "Madhya Pradesh", "Punjab", "Haryana", "Bihar",
        ]
        for s in states:
            if s.lower() in snippet.lower():
                state = s
                break

        # Extract phone if present
        phone = None
        phone_match = re.search(r'(?:tel|phone|call)[:\s]*([+\d\s-]{10,})', snippet, re.IGNORECASE)
        if phone_match:
            phone = re.sub(r'[^\d+]', '', phone_match.group(1))

        # Extract email if present
        email = None
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', snippet)
        if email_match:
            email = email_match.group(0).lower()

        return {
            "company_name": title,
            "website": url,
            "phone": phone,
            "email": email,
            "city": city,
            "state": state,
            "country": "India",
            "source": "google",
            "crawl_date": datetime.now(timezone.utc).isoformat(),
        }

    def _extract_indiamart_from_html(self, html: str) -> list[dict]:
        """Extract IndiaMART company data from search results."""
        companies = []

        # Find IndiaMART listing links
        pattern = r'indiamart\.com/([^/]+)/([^"&]+)'
        matches = re.findall(pattern, html)

        for domain, slug in matches:
            name = slug.replace("-", " ").replace(".html", "").title()
            if len(name) > 3:
                companies.append({
                    "company_name": name,
                    "website": f"https://www.indiamart.com/{domain}/{slug}",
                    "source": "indiamart",
                    "country": "India",
                    "crawl_date": datetime.now(timezone.utc).isoformat(),
                })

        return companies

    async def close(self):
        await self.client.aclose()
