"""
BuyerHunter AI — Website Enrichment Crawler

Deep-crawls company websites to extract:
- About Us, Products, Brands, Industries Served
- Contact/Careers pages, Procurement info
- Company description and metadata
"""

import re
import json
import logging
import asyncio
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field, asdict

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Common page paths to search
ABOUT_PATHS = ["/about", "/about-us", "/about.html", "/about/", "/company", "/our-story"]
PRODUCTS_PATHS = ["/products", "/services", "/solutions", "/offerings", "/catalog", "/product"]
CONTACT_PATHS = ["/contact", "/contact-us", "/contact.html", "/reach-us", "/get-in-touch"]
CAREERS_PATHS = ["/careers", "/jobs", "/join-us", "/work-with-us", "/vacancies", "/opportunities"]
PROCUREMENT_PATHS = ["/procurement", "/vendor", "/supplier", "/tender", "/purchase"]

OIL_KEYWORDS = [
    "oil", "edible", "cooking", "palm", "sunflower", "soybean", "mustard",
    "groundnut", "coconut", "canola", "rice bran", "refined", "vegetable",
    "frying", "bakery", "snack", "namkeen", "confectionery", "food processing",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass
class EnrichmentData:
    """Structured enrichment data extracted from a company website."""
    about_us: str = ""
    products: list = field(default_factory=list)
    brands: list = field(default_factory=list)
    industries_served: list = field(default_factory=list)
    company_description: str = ""
    contact_page: str = ""
    careers_page: str = ""
    procurement_info: str = ""
    phones: list = field(default_factory=list)
    emails: list = field(default_factory=list)
    address: str = ""
    city: str = ""
    state: str = ""

    def to_dict(self):
        d = asdict(self)
        d["products"] = json.dumps(d["products"])
        d["brands"] = json.dumps(d["brands"])
        d["industries_served"] = json.dumps(d["industries_served"])
        return d


class WebsiteEnricher:
    """Enriches company data by crawling their website."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._client = None

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def enrich(self, website_url: str) -> EnrichmentData:
        """Crawl a company website and extract enrichment data."""
        data = EnrichmentData()

        if not website_url:
            return data

        base_url = self._normalize_url(website_url)
        if not base_url:
            return data

        try:
            client = await self._get_client()

            # Crawl main page
            main_html = await self._fetch(client, base_url)
            if main_html:
                self._extract_from_page(main_html, base_url, data, is_main=True)

            # Discover and crawl subpages
            soup = BeautifulSoup(main_html or "", "lxml")
            all_links = self._extract_links(soup, base_url)

            # Crawl About page
            about_url = self._find_page(base_url, all_links, ABOUT_PATHS)
            if about_url:
                html = await self._fetch(client, about_url)
                if html:
                    self._extract_about(html, data)

            # Crawl Products page
            products_url = self._find_page(base_url, all_links, PRODUCTS_PATHS)
            if products_url:
                html = await self._fetch(client, products_url)
                if html:
                    self._extract_products(html, data)

            # Find Contact page
            contact_url = self._find_page(base_url, all_links, CONTACT_PATHS)
            if contact_url:
                data.contact_page = contact_url
                html = await self._fetch(client, contact_url)
                if html:
                    self._extract_contact(html, data)

            # Find Careers page
            careers_url = self._find_page(base_url, all_links, CAREERS_PATHS)
            if careers_url:
                data.careers_page = careers_url

            # Find Procurement page
            proc_url = self._find_page(base_url, all_links, PROCUREMENT_PATHS)
            if proc_url:
                html = await self._fetch(client, proc_url)
                if html:
                    self._extract_procurement(html, data)

        except Exception as e:
            logger.error(f"Enrichment failed for {website_url}: {e}")

        return data

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "text/html" in content_type:
                    return resp.text
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
        return None

    def _normalize_url(self, url: str) -> str | None:
        url = url.strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full = urljoin(base_url, href)
            parsed = urlparse(full)
            base_parsed = urlparse(base_url)
            if parsed.netloc == base_parsed.netloc:
                links.append(full)
        return list(set(links))

    def _find_page(self, base_url: str, links: list[str], paths: list[str]) -> str | None:
        base_parsed = urlparse(base_url)
        base_path = base_parsed.path.rstrip("/")

        for path in paths:
            # Check if path is in any discovered link
            for link in links:
                link_parsed = urlparse(link)
                link_path = link_parsed.path.rstrip("/")
                if link_path.endswith(path) or link_path == path:
                    return link

            # Try direct URL construction
            test_url = f"{base_url.rstrip('/')}{path}"
            if test_url not in links:
                continue

        # Try direct fetch of common paths
        for path in paths:
            test_url = f"{base_url.rstrip('/')}{path}"
            return test_url

        return None

    def _extract_from_page(self, html: str, base_url: str, data: EnrichmentData, is_main: bool = False):
        soup = BeautifulSoup(html, "lxml")

        # Extract meta description as company description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            data.company_description = meta_desc["content"].strip()

        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content") and not data.company_description:
            data.company_description = og_desc["content"].strip()

        # Extract text content for analysis
        text = soup.get_text(separator=" ", strip=True)

        # Extract emails and phones
        self._extract_contact_data(soup, text, data)

        # Extract address
        self._extract_address(soup, data)

    def _extract_about(self, html: str, data: EnrichmentData):
        soup = BeautifulSoup(html, "lxml")

        # Remove nav, footer, header
        for tag in soup.find_all(["nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        # Truncate to reasonable length
        if len(text) > 3000:
            sentences = text[:3000].rsplit(".", 1)
            text = sentences[0] + "." if len(sentences) > 1 else sentences[0]

        data.about_us = text

    def _extract_products(self, html: str, data: EnrichmentData):
        soup = BeautifulSoup(html, "lxml")

        # Try various product listing patterns
        products = set()

        # Look for product cards/tiles
        for selector in [
            "div.product-name", "h3.product-title", "span.product-name",
            "div.card-title", "h4", "li.product", "div.service-name",
        ]:
            for el in soup.select(selector):
                text = el.get_text(strip=True)
                if text and len(text) < 100:
                    products.add(text)

        # Look for list items that might be products
        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            if text and len(text) < 60 and any(kw in text.lower() for kw in OIL_KEYWORDS):
                products.add(text)

        data.products = list(products)[:20]

    def _extract_contact(self, html: str, data: EnrichmentData):
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        self._extract_contact_data(soup, text, data)

    def _extract_procurement(self, html: str, data: EnrichmentData):
        soup = BeautifulSoup(html, "lxml")

        for tag in soup.find_all(["nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        if len(text) > 2000:
            text = text[:2000]

        data.procurement_info = text

    def _extract_contact_data(self, soup: BeautifulSoup, text: str, data: EnrichmentData):
        # Extract emails
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        emails = set(email_pattern.findall(text))
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("mailto:"):
                email = a["href"].replace("mailto:", "").split("?")[0].strip()
                emails.add(email)
        data.emails = [e.lower() for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg"))]

        # Extract phones
        phone_pattern = re.compile(r"(?:\+91|91|0)?[\s-]?\d{10}|\d{5}[\s-]\d{5}")
        phones = set(phone_pattern.findall(text))
        for a in soup.find_all("a", href=True):
            if a["href"].startswith("tel:"):
                phone = a["href"].replace("tel:", "").strip()
                phones.add(phone)
        data.phones = [re.sub(r"[^\d+]", "", p) for p in phones if len(re.sub(r"[^\d]", "", p)) >= 10]

    def _extract_address(self, soup: BeautifulSoup, data: EnrichmentData):
        # Look for address elements
        addr_el = soup.find("address")
        if addr_el:
            data.address = addr_el.get_text(separator=", ", strip=True)

        # Look for itemprop address
        addr_el = soup.find(attrs={"itemprop": "address"})
        if addr_el and not data.address:
            data.address = addr_el.get_text(separator=", ", strip=True)

        # Look for common address classes
        for cls in ["address", "location", "office-address", "registered-address"]:
            el = soup.find(class_=re.compile(cls, re.I))
            if el and not data.address:
                data.address = el.get_text(separator=", ", strip=True)

        # Parse city/state from address
        if data.address:
            parts = [p.strip() for p in data.address.split(",")]
            if parts:
                data.city = parts[0].title() if len(parts[0]) > 2 else (parts[1].title() if len(parts) > 1 else "")
            if len(parts) > 1:
                data.state = parts[-1].title()

    async def enrich_batch(self, websites: list[str], concurrency: int = 3) -> list[EnrichmentData]:
        """Enrich multiple websites with concurrency control."""
        semaphore = asyncio.Semaphore(concurrency)
        results = []

        async def _enrich_one(url):
            async with semaphore:
                return await self.enrich(url)

        tasks = [_enrich_one(url) for url in websites if url]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if isinstance(r, EnrichmentData) else EnrichmentData()
            for r in results
        ]
