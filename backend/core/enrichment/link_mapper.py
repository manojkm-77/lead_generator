"""
BuyerHunter V2 — Deep Website Enrichment Map

Recursive link crawler that takes a discovered root company website
and cleanly traces paths to map deep nodes up to max_depth=2.

Maps: /about, /contact, /products, /brands, /team, etc.
Extracts: company metadata, contact channels, product lines,
social links, and structured data (JSON-LD, OpenGraph).
"""

import re
import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Page classification paths ────────────────────────────────────────────────

PAGE_CATEGORIES: dict[str, list[str]] = {
    "about": ["/about", "/about-us", "/about.html", "/about/",
              "/company", "/our-story", "/overview", "/profile"],
    "contact": ["/contact", "/contact-us", "/contact.html", "/contact/",
                "/reach-us", "/get-in-touch", "/enquiry"],
    "products": ["/products", "/services", "/solutions", "/offerings",
                 "/product", "/catalog", "/catalogue", "/product-lines"],
    "brands": ["/brands", "/our-brands", "/brand", "/product-brands"],
    "team": ["/team", "/leadership", "/management", "/board", "/about/team"],
    "careers": ["/careers", "/jobs", "/join-us", "/work-with-us",
                "/vacancies", "/opportunities"],
    "procurement": ["/procurement", "/vendor", "/supplier", "/tender",
                    "/purchase", "/buying"],
}

# ── Data models ──────────────────────────────────────────────────────────────

@dataclass
class MappedPage:
    """A single crawled page with its classification and extracted data."""
    url: str
    category: str = "other"          # about, contact, products, brands, etc.
    title: str = ""
    meta_description: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    products_mentioned: list[str] = field(default_factory=list)
    json_ld: list[dict] = field(default_factory=list)
    open_graph: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""
    depth: int = 0
    status_code: int = 0


@dataclass
class MappedSite:
    """
    Complete map of a company website.
    Contains all discovered pages classified by category.
    """
    root_url: str
    domain: str = ""
    pages: list[MappedPage] = field(default_factory=list)

    # Aggregated data
    company_name: str = ""
    description: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    products: list[str] = field(default_factory=list)
    json_ld_org: dict | None = None

    # Metadata
    pages_crawled: int = 0
    max_depth_reached: int = 0
    errors: list[str] = field(default_factory=list)

    def get_pages_by_category(self, category: str) -> list[MappedPage]:
        """Get all pages matching a category."""
        return [p for p in self.pages if p.category == category]

    def get_contact_page(self) -> MappedPage | None:
        """Get the contact page if found."""
        pages = self.get_pages_by_category("contact")
        return pages[0] if pages else None

    def get_about_page(self) -> MappedPage | None:
        """Get the about page if found."""
        pages = self.get_pages_by_category("about")
        return pages[0] if pages else None

    def get_product_pages(self) -> list[MappedPage]:
        """Get all product-related pages."""
        return self.get_pages_by_category("products") + self.get_pages_by_category("brands")


# ── Link Mapper ──────────────────────────────────────────────────────────────

class LinkMapper:
    """
    Recursive website mapper. Takes a root URL and traces internal links
    up to max_depth to build a complete site map.

    Features:
      - Domain-scoped crawling (stays within the target site)
      - Page classification by URL path and content
      - Contact data extraction (emails, phones, social links)
      - JSON-LD structured data extraction
      - OpenGraph metadata extraction
      - Rate limiting via delay between requests
    """

    def __init__(
        self,
        max_depth: int = 2,
        max_pages: int = 30,
        timeout: int = 15,
        delay: float = 0.5,
    ):
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay = delay

    async def map_site(self, root_url: str) -> MappedSite:
        """
        Map a company website starting from the root URL.

        Crawls internal links recursively up to max_depth,
        classifies pages, and extracts contact/metadata.

        Args:
            root_url: The company's homepage URL

        Returns:
            MappedSite with all discovered pages and aggregated data
        """
        root_url = self._normalize_url(root_url)
        if not root_url:
            return MappedSite(root_url="", errors=["Invalid root URL"])

        parsed = urlparse(root_url)
        domain = parsed.netloc
        site = MappedSite(root_url=root_url, domain=domain)

        visited: set[str] = set()
        queue: list[tuple[str, int]] = [(root_url, 0)]  # (url, depth)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        import asyncio

        async with httpx.AsyncClient(
            headers=headers, timeout=self.timeout,
            follow_redirects=True, verify=False,
        ) as client:
            while queue and len(visited) < self.max_pages:
                url, depth = queue.pop(0)

                # Normalize and check
                url_key = url.rstrip("/").lower()
                if url_key in visited:
                    continue
                if depth > self.max_depth:
                    continue

                visited.add(url_key)
                site.pages_crawled += 1
                site.max_depth_reached = max(site.max_depth_reached, depth)

                # Fetch page
                try:
                    resp = await client.get(url)
                    content_type = resp.headers.get("content-type", "")
                    if resp.status_code != 200 or "text/html" not in content_type:
                        continue

                    # Parse
                    page = self._parse_page(url, resp.text, resp.status_code, depth)
                    site.pages.append(page)

                    # Extract internal links for next depth level
                    if depth < self.max_depth:
                        new_links = self._extract_internal_links(
                            resp.text, url, domain
                        )
                        for link in new_links:
                            if link.rstrip("/").lower() not in visited:
                                queue.append((link, depth + 1))

                    # Rate limit
                    if self.delay > 0:
                        await asyncio.sleep(self.delay)

                except Exception as e:
                    site.errors.append(f"Failed to crawl {url}: {e}")
                    logger.debug(f"Map crawl failed for {url}: {e}")

        # Aggregate data across all pages
        self._aggregate(site)

        logger.info(
            f"Mapped {domain}: {site.pages_crawled} pages, "
            f"depth={site.max_depth_reached}, "
            f"{len(site.emails)} emails, {len(site.phones)} phones"
        )
        return site

    # ── Page parsing ─────────────────────────────────────────────────────────

    def _parse_page(
        self, url: str, html: str, status_code: int, depth: int,
    ) -> MappedPage:
        """Parse a single page into a MappedPage."""
        soup = BeautifulSoup(html, "lxml")
        page = MappedPage(url=url, depth=depth, status_code=status_code)

        # Category by URL path
        page.category = self._classify_page(url)

        # Title
        title_el = soup.select_one("title")
        if title_el:
            page.title = title_el.get_text(strip=True)[:200]

        # Meta description
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc:
            page.meta_description = meta_desc.get("content", "")[:500]

        # Extract text content (cleaned)
        for tag in soup.find_all(["nav", "footer", "header", "aside", "script", "style"]):
            tag.decompose()
        page.raw_text = soup.get_text(separator=" ", strip=True)[:5000]

        # Emails
        page.emails = self._extract_emails(soup)

        # Phones
        page.phones = self._extract_phones(soup)

        # Social links
        page.social_links = self._extract_social_links(soup)

        # Products mentioned
        page.products_mentioned = self._extract_product_mentions(page.raw_text)

        # JSON-LD structured data
        page.json_ld = self._extract_json_ld(soup)

        # OpenGraph
        page.open_graph = self._extract_open_graph(soup)

        return page

    def _classify_page(self, url: str) -> str:
        """Classify a page by its URL path."""
        parsed = urlparse(url)
        path = parsed.path.lower().rstrip("/")

        for category, patterns in PAGE_CATEGORIES.items():
            for pattern in patterns:
                if path.endswith(pattern.rstrip("/")) or path == pattern.rstrip("/"):
                    return category

        return "other"

    def _extract_internal_links(
        self, html: str, current_url: str, target_domain: str,
    ) -> list[str]:
        """Extract same-domain links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(current_url, href)
            parsed = urlparse(full_url)

            # Must be same domain
            if parsed.netloc != target_domain:
                continue

            # Skip non-HTML resources
            path = parsed.path.lower()
            skip_ext = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg",
                        ".css", ".js", ".zip", ".doc", ".docx", ".xls")
            if any(path.endswith(ext) for ext in skip_ext):
                continue

            # Normalize: strip fragment, trailing slash
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"
            if parsed.query:
                clean += f"?{parsed.query}"

            links.append(clean)

        return list(set(links))

    # ── Data extraction helpers ──────────────────────────────────────────────

    def _extract_emails(self, soup: BeautifulSoup) -> list[str]:
        """Extract unique emails from page."""
        emails: set[str] = set()

        # mailto links
        for a_tag in soup.find_all("a", href=True):
            if a_tag["href"].startswith("mailto:"):
                email = a_tag["href"].replace("mailto:", "").split("?")[0].strip()
                emails.add(email.lower())

        # Regex in text
        text = soup.get_text()
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        for match in email_pattern.findall(text):
            emails.add(match.lower())

        # Filter out image/css artifacts
        return [e for e in emails
                if not e.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".ico"))]

    def _extract_phones(self, soup: BeautifulSoup) -> list[str]:
        """Extract unique phone numbers from page."""
        phones: set[str] = set()

        # tel: links
        for a_tag in soup.find_all("a", href=True):
            if a_tag["href"].startswith("tel:"):
                phone = a_tag["href"].replace("tel:", "").strip()
                digits = re.sub(r"[^\d+]", "", phone)
                if len(digits) >= 10:
                    phones.add(digits)

        # Regex in text
        text = soup.get_text()
        phone_pattern = re.compile(r"(?:\+91|91|0)?[\s-]?\d{10}")
        for match in phone_pattern.findall(text):
            digits = re.sub(r"[^\d]", "", match)
            if len(digits) >= 10:
                phones.add(digits)

        return list(phones)

    def _extract_social_links(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract social media links."""
        social: dict[str, str] = {}

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].lower()
            if "linkedin.com" in href and "linkedin" not in social:
                social["linkedin"] = a_tag["href"]
            elif "facebook.com" in href and "facebook" not in social:
                social["facebook"] = a_tag["href"]
            elif "instagram.com" in href and "instagram" not in social:
                social["instagram"] = a_tag["href"]
            elif "twitter.com" in href or "x.com" in href:
                if "twitter" not in social:
                    social["twitter"] = a_tag["href"]
            elif "youtube.com" in href and "youtube" not in social:
                social["youtube"] = a_tag["href"]

        return social

    def _extract_product_mentions(self, text: str) -> list[str]:
        """Extract product/brand mentions from page text."""
        oil_keywords = [
            "palm oil", "sunflower oil", "soybean oil", "mustard oil",
            "coconut oil", "groundnut oil", "rice bran oil", "edible oil",
            "cooking oil", "vegetable oil", "vanaspati", "shortening",
            "margarine", "soap", "detergent", "bakery", "snack",
        ]

        text_lower = text.lower()
        found = [kw for kw in oil_keywords if kw in text_lower]
        return list(set(found))

    def _extract_json_ld(self, soup: BeautifulSoup) -> list[dict]:
        """Extract JSON-LD structured data."""
        import json

        results: list[dict] = []
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    results.append(data)
                elif isinstance(data, list):
                    results.extend(data)
            except (json.JSONDecodeError, TypeError):
                pass

        return results

    def _extract_open_graph(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract OpenGraph metadata."""
        og: dict[str, str] = {}

        for meta in soup.select("meta[property^='og:']"):
            prop = meta.get("property", "").replace("og:", "")
            content = meta.get("content", "")
            if prop and content:
                og[prop] = content

        return og

    # ── Aggregation ──────────────────────────────────────────────────────────

    def _aggregate(self, site: MappedSite) -> None:
        """Aggregate data across all mapped pages into site-level fields."""
        all_emails: set[str] = set()
        all_phones: set[str] = set()
        all_social: dict[str, str] = {}
        all_products: set[str] = set()

        # Collect from all pages
        for page in site.pages:
            all_emails.update(page.emails)
            all_phones.update(page.phones)
            all_social.update(page.social_links)
            all_products.update(page.products_mentioned)

            # Extract org name from JSON-LD
            for ld in page.json_ld:
                if ld.get("@type") in ("Organization", "LocalBusiness", "Corporation"):
                    if not site.json_ld_org:
                        site.json_ld_org = ld
                    if not site.company_name and ld.get("name"):
                        site.company_name = ld["name"]

        # Site-level aggregation
        site.emails = sorted(all_emails)
        site.phones = sorted(all_phones)
        site.social_links = all_social
        site.products = sorted(all_products)

        # Company name from JSON-LD or first page title
        if not site.company_name:
            about = site.get_about_page()
            if about and about.title:
                # Clean: "About Us | Company Name" → "Company Name"
                parts = about.title.split("|")
                if len(parts) > 1:
                    site.company_name = parts[-1].strip()
                else:
                    parts = about.title.split(" - ")
                    site.company_name = parts[-1].strip() if len(parts) > 1 else about.title

        # Description from JSON-LD or meta
        if site.json_ld_org and site.json_ld_org.get("description"):
            site.description = site.json_ld_org["description"]
        else:
            about = site.get_about_page()
            if about and about.meta_description:
                site.description = about.meta_description

    # ── Utilities ────────────────────────────────────────────────────────────

    def _normalize_url(self, url: str) -> str | None:
        """Normalize and validate a URL."""
        url = url.strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}"
