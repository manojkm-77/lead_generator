"""
BuyerHunter AI — Procurement Contact Discovery

Discovers procurement-related contacts from company websites.
Only extracts publicly available information.
"""

import re
import logging
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PROCUREMENT_TITLES = [
    "procurement", "purchase", "buying", "sourcing", "supply chain",
    "commercial", "import", "factory", "operations", "production",
    "manufacturing", "general manager", "director", "owner", "founder",
    "ceo", "managing director", "chief", "head of",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class DiscoveredContact:
    name: str
    designation: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    source_url: str = ""
    confidence: int = 50


class ProcurementContactDiscovery:
    """Discovers procurement contacts from company websites."""

    TEAM_PATHS = ["/team", "/leadership", "/management", "/about/team", "/about/leadership",
                  "/our-team", "/people", "/founders", "/management-team"]
    CONTACT_PATHS = ["/contact", "/contact-us", "/reach-us"]
    ABOUT_PATHS = ["/about", "/about-us", "/about/management"]

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self._client = None

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=HEADERS, timeout=self.timeout,
                follow_redirects=True, verify=False,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def discover(self, website_url: str) -> list[DiscoveredContact]:
        """Discover procurement contacts from a company website."""
        contacts = []
        base_url = self._normalize_url(website_url)
        if not base_url:
            return contacts

        client = await self._get_client()

        # Crawl team/leadership pages
        for paths in [self.TEAM_PATHS, self.ABOUT_PATHS, self.CONTACT_PATHS]:
            for path in paths:
                url = f"{base_url.rstrip('/')}{path}"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                        page_contacts = self._extract_contacts(resp.text, url)
                        contacts.extend(page_contacts)
                except Exception:
                    continue

        # Also scan main page for team info
        try:
            resp = await client.get(base_url)
            if resp.status_code == 200:
                main_contacts = self._extract_contacts(resp.text, base_url)
                contacts.extend(main_contacts)
        except Exception:
            pass

        # Deduplicate by name+email
        seen = set()
        unique = []
        for c in contacts:
            key = (c.name.lower(), c.email.lower())
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # Score confidence
        for c in unique:
            c.confidence = self._score_confidence(c)

        return sorted(unique, key=lambda x: x.confidence, reverse=True)

    def _extract_contacts(self, html: str, source_url: str) -> list[DiscoveredContact]:
        soup = BeautifulSoup(html, "lxml")
        contacts = []

        # Method 1: Look for team member cards
        for card in soup.select("div.team-member, div.person, div.staff, div.leaderhip-card, li.team"):
            contact = self._extract_from_card(card, source_url)
            if contact:
                contacts.append(contact)

        # Method 2: Look for structured data
        for item in soup.select("[itemtype*='Person'], [itemtype*='Organization']"):
            contact = self._extract_from_schema(item, source_url)
            if contact:
                contacts.append(contact)

        # Method 3: Extract from text patterns
        text_contacts = self._extract_from_text(soup.get_text(), source_url)
        contacts.extend(text_contacts)

        # Method 4: Look for email patterns near names
        email_contacts = self._extract_emails_with_context(soup, source_url)
        contacts.extend(email_contacts)

        return contacts

    def _extract_from_card(self, card, source_url: str) -> DiscoveredContact | None:
        name = self._clean(
            card.select_one("h3, h4, h5, .name, .person-name, .staff-name")
        )
        if not name:
            return None

        designation = self._clean(
            card.select_one(".designation, .title, .role, .position, .job-title")
        )

        email_el = card.select_one("a[href^='mailto:']")
        email = email_el["href"].replace("mailto:", "").split("?")[0] if email_el else ""

        phone_el = card.select_one("a[href^='tel:']")
        phone = phone_el["href"].replace("tel:", "") if phone_el else ""

        linkedin_el = card.select_one("a[href*='linkedin.com']")
        linkedin = linkedin_el["href"] if linkedin_el else ""

        return DiscoveredContact(
            name=name, designation=designation or "",
            email=email, phone=phone,
            linkedin_url=linkedin, source_url=source_url,
        )

    def _extract_from_schema(self, item, source_url: str) -> DiscoveredContact | None:
        name = self._clean(item.select_one("[itemprop='name'], .name"))
        if not name:
            return None

        designation = self._clean(item.select_one("[itemprop='jobTitle'], .title"))
        email_el = item.select_one("[itemprop='email'], a[href^='mailto:']")
        email = ""
        if email_el:
            email = email_el.get("content", "") or email_el["href"].replace("mailto:", "")

        return DiscoveredContact(
            name=name, designation=designation or "",
            email=email, source_url=source_url,
        )

    def _extract_from_text(self, text: str, source_url: str) -> list[DiscoveredContact]:
        contacts = []
        # Pattern: Name - Designation
        pattern = r"([A-Z][a-z]+ [A-Z][a-z]+)\s*[-–—]\s*(Procurement|Purchase|Supply Chain|Commercial|Factory|Operations|Director|Manager|CEO|Owner|Founder)"
        for match in re.finditer(pattern, text):
            name, designation = match.groups()
            contacts.append(DiscoveredContact(
                name=name.strip(), designation=designation.strip(),
                source_url=source_url, confidence=40,
            ))
        return contacts

    def _extract_emails_with_context(self, soup: BeautifulSoup, source_url: str) -> list[DiscoveredContact]:
        contacts = []
        for a in soup.select("a[href^='mailto:']"):
            email = a["href"].replace("mailto:", "").split("?")[0]
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                continue

            # Look for nearby name
            parent = a.parent
            for _ in range(3):
                if parent is None:
                    break
                text = parent.get_text(" ", strip=True)
                name_match = re.search(r"([A-Z][a-z]+ [A-Z][a-z]+)", text)
                if name_match:
                    name = name_match.group(1)
                    designation = self._guess_designation(text)
                    contacts.append(DiscoveredContact(
                        name=name, designation=designation,
                        email=email, source_url=source_url, confidence=45,
                    ))
                    break
                parent = parent.parent

        return contacts

    def _guess_designation(self, text: str) -> str:
        text_lower = text.lower()
        for title in PROCUREMENT_TITLES:
            if title in text_lower:
                return title.title()
        return ""

    def _score_confidence(self, contact: DiscoveredContact) -> int:
        score = 30
        designation = (contact.designation or "").lower()

        # Higher score for procurement-related titles
        for title in ["procurement", "purchase", "buying", "sourcing", "supply chain", "commercial"]:
            if title in designation:
                score += 30
                break

        # Medium score for management titles
        for title in ["director", "manager", "head", "chief", "ceo", "owner", "founder"]:
            if title in designation:
                score += 20
                break

        # Bonus for email
        if contact.email:
            score += 10

        # Bonus for LinkedIn
        if contact.linkedin_url:
            score += 5

        # Bonus for phone
        if contact.phone:
            score += 5

        return min(100, score)

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

    def _clean(self, el) -> str:
        if el is None:
            return ""
        text = el.get_text(strip=True) if hasattr(el, "get_text") else str(el)
        return re.sub(r"\s+", " ", text).strip()
