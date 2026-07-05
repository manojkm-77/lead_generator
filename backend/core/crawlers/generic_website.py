"""
BuyerHunter V2 — Generic Corporate Website Crawler Adapter

Crawls arbitrary company websites to extract structured business data.
Used as a fallback for companies discovered via other sources
that have their own websites.
"""

import re
import logging
from urllib.parse import urljoin, urlparse

from backend.core.crawlers.base import BaseCrawlerAdapter, CrawledEntity

logger = logging.getLogger(__name__)


class GenericCorporateWebsiteAdapter(BaseCrawlerAdapter):
    """
    Adapter for generic corporate websites.
    Extracts contact info, about pages, product listings, and company metadata.
    """

    @property
    def adapter_name(self) -> str:
        return "generic_website"

    @property
    def display_name(self) -> str:
        return "Corporate Website"

    @property
    def source_type(self) -> str:
        return "corporate_website"

    @property
    def base_url(self) -> str:
        return ""  # Dynamic per target

    @property
    def default_priority(self) -> int:
        return 5

    @property
    def rate_limit_seconds(self) -> float:
        return 2.0

    async def search(self, query: str, **kwargs) -> list[str]:
        """
        For generic websites, the 'query' IS the URL to crawl.
        Accepts a website URL directly.
        """
        url = kwargs.get("url", query)
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return [url]

    async def discover_urls(self, search_result_urls: list[str], **kwargs) -> list[str]:
        """
        Discover subpages to crawl from the root URL:
          /about, /contact, /products, /brands, etc.
        """
        all_urls: list[str] = []
        max_depth = kwargs.get("max_depth", 2)

        for root_url in search_result_urls:
            all_urls.append(root_url)
            subpages = await self._discover_subpages(root_url, max_depth=max_depth)
            all_urls.extend(subpages)

        return all_urls

    async def _discover_subpages(self, root_url: str, max_depth: int = 2) -> list[str]:
        """Recursive subpage discovery up to max_depth."""
        import httpx

        COMMON_PATHS = [
            "/about", "/about-us", "/about.html", "/about/",
            "/contact", "/contact-us", "/contact.html",
            "/products", "/services", "/solutions", "/offerings",
            "/brands", "/product-lines",
            "/team", "/leadership", "/management",
            "/careers", "/jobs",
        ]

        discovered: list[str] = []
        base_parsed = urlparse(root_url)
        base_domain = base_parsed.netloc

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        try:
            async with httpx.AsyncClient(
                headers=headers, timeout=10, follow_redirects=True, verify=False,
            ) as client:
                resp = await client.get(root_url)
                if resp.status_code != 200:
                    return discovered

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "lxml")

                # Extract all same-domain links
                links = set()
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    full_url = urljoin(root_url, href)
                    parsed = urlparse(full_url)

                    # Stay on same domain
                    if parsed.netloc != base_domain:
                        continue

                    # Strip fragment, normalize
                    clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
                    if clean != root_url.rstrip("/"):
                        links.add(clean)

                # Add common paths if not already found
                for path in COMMON_PATHS:
                    candidate = f"{root_url.rstrip('/')}{path}"
                    if candidate not in links:
                        links.add(candidate)

                discovered = list(links)[:30]  # Cap at 30 subpages

        except Exception as e:
            logger.debug(f"Subpage discovery failed for {root_url}: {e}")

        return discovered

    async def crawl(self, entity_urls: list[str], **kwargs) -> list[dict]:
        import httpx

        pages: list[dict] = []
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(
            headers=headers, timeout=15, follow_redirects=True, verify=False,
        ) as client:
            for url in entity_urls:
                try:
                    resp = await client.get(url)
                    content_type = resp.headers.get("content-type", "")
                    if resp.status_code == 200 and "text/html" in content_type:
                        pages.append({
                            "url": str(resp.url),
                            "html": resp.text,
                            "status_code": resp.status_code,
                        })
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {e}")

        return pages

    async def extract(self, raw_pages: list[dict], **kwargs) -> list[dict]:
        """Extract structured data from corporate website pages."""
        from bs4 import BeautifulSoup

        records: list[dict] = []

        for page in raw_pages:
            html = page.get("html", "")
            url = page.get("url", "")
            if not html:
                continue

            soup = BeautifulSoup(html, "lxml")
            record: dict = {"source_url": url}

            # Company name from title or h1
            title_el = soup.select_one("title")
            if title_el:
                title_text = title_el.get_text(strip=True)
                # Clean: remove " | Company Name" suffixes
                parts = title_text.split("|")
                if len(parts) > 1:
                    record["company_name"] = parts[-1].strip()
                else:
                    parts = title_text.split(" - ")
                    record["company_name"] = parts[-1].strip() if len(parts) > 1 else title_text

            h1_el = soup.select_one("h1")
            if h1_el and not record.get("company_name"):
                record["company_name"] = h1_el.get_text(strip=True)

            # Meta description
            meta_desc = soup.select_one("meta[name='description']")
            if meta_desc:
                record["description"] = meta_desc.get("content", "")

            # Emails
            emails = set()
            for a_tag in soup.find_all("a", href=True):
                if a_tag["href"].startswith("mailto:"):
                    email = a_tag["href"].replace("mailto:", "").split("?")[0].strip()
                    emails.add(email.lower())

            email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
            for email in email_pattern.findall(soup.get_text()):
                emails.add(email.lower())

            record["emails"] = [e for e in emails
                                if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css"))]

            # Phones
            phones = set()
            for a_tag in soup.find_all("a", href=True):
                if a_tag["href"].startswith("tel:"):
                    phone = a_tag["href"].replace("tel:", "").strip()
                    phones.add(phone)

            phone_pattern = re.compile(r"(?:\+91|91|0)?[\s-]?\d{10}")
            for phone in phone_pattern.findall(soup.get_text()):
                phones.add(phone)

            record["phones"] = list(phones)

            # Address
            addr_el = soup.select_one("address")
            if addr_el:
                record["address"] = addr_el.get_text(separator=", ", strip=True)

            # Social links
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if "linkedin.com" in href:
                    record["linkedin_url"] = href
                elif "facebook.com" in href:
                    record["facebook_url"] = href
                elif "instagram.com" in href:
                    record["instagram_url"] = href

            if record.get("company_name"):
                records.append(record)

        return records

    async def normalize(self, raw_data: list[dict], **kwargs) -> list[CrawledEntity]:
        entities: list[CrawledEntity] = []

        for record in raw_data:
            name = record.get("company_name", "").strip()
            if not name:
                continue

            # Parse address for city/state
            address = record.get("address", "")
            city, state = self._parse_address(address)

            # Normalize emails and phones
            emails = [self._normalize_email(e) for e in record.get("emails", [])]
            emails = [e for e in emails if e]

            phones = [self._normalize_phone(p) for p in record.get("phones", [])]
            phones = [p for p in phones if p]

            entities.append(CrawledEntity(
                canonical_name=name,
                website_url=record.get("source_url", ""),
                emails=emails,
                phones=phones,
                hq_state=state,
                hq_city=city,
                hq_address=address,
                description=record.get("description", ""),
                linkedin_urls=[record.get("linkedin_url", "")] if record.get("linkedin_url") else [],
                source=self.adapter_name,
                source_url=record.get("source_url", ""),
            ))

        return entities

    def _parse_address(self, address: str) -> tuple[str, str]:
        """Best-effort city/state extraction from address string."""
        if not address:
            return "", ""
        parts = [p.strip() for p in address.split(",")]
        # Common Indian address: "Street, City, State PIN"
        city = ""
        state = ""
        if len(parts) >= 2:
            city = parts[-2] if len(parts[-2]) > 2 else (parts[-3] if len(parts) >= 3 else "")
            state = parts[-1]
            # Strip pincode from state
            state = re.sub(r"\d{6}$", "", state).strip()
        elif len(parts) == 1:
            city = parts[0]
        return city, state
