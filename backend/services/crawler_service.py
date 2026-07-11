"""
BuyerHunter Multi-Source Crawler Service

Playwright + httpx crawlers for Indian business directories.
Playwright for JS-heavy sites (TradeIndia, JustDial, IndiaMART, GoogleMaps).
httpx fallback for simple HTML sites (ExportersIndia, YellowPages, APEDA, GST).
"""

import asyncio
import json
import logging
import re
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

import httpx
from bs4 import BeautifulSoup

from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

_BROWSER = None
_PLAY = None


async def _get_playwright():
    global _PLAY
    if _PLAY is None:
        _PLAY = await async_playwright().start()
    return _PLAY


async def _get_browser():
    global _BROWSER
    if _BROWSER is None or not _BROWSER.is_connected():
        pw = await _get_playwright()
        _BROWSER = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
    return _BROWSER


async def close_global_browser():
    global _BROWSER, _PLAY
    if _BROWSER:
        try:
            await _BROWSER.close()
        except Exception:
            pass
        _BROWSER = None
    if _PLAY:
        try:
            await _PLAY.stop()
        except Exception:
            pass
        _PLAY = None


@dataclass
class ExtractedCompany:
    company_name: str = ""
    website: str = ""
    email: str = ""
    phone: str = ""
    whatsapp: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    country: str = "India"
    industry: str = ""
    products: str = ""
    source: str = ""
    source_url: str = ""
    confidence: int = 50
    crawl_timestamp: str = ""


@dataclass
class ExtractedContact:
    person_name: str = ""
    designation: str = ""
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""
    source_url: str = ""
    confidence: int = 50


@dataclass
class CrawlResult:
    companies: list[ExtractedCompany] = field(default_factory=list)
    contacts: list[ExtractedContact] = field(default_factory=list)
    pages_crawled: int = 0
    errors: list[str] = field(default_factory=list)


class MultiSourceCrawler:
    def __init__(self, timeout: int = 30, max_pages: int = 3):
        self.timeout = timeout
        self.max_pages = max_pages
        self._client: httpx.AsyncClient | None = None

    async def _get_httpx(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=15, read=20),
                follow_redirects=True,
                verify=False,
                headers={"Accept-Language": "en-US,en;q=0.9"},
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _fetch(self, url: str, headers: dict | None = None) -> str | None:
        client = await self._get_httpx()
        h = headers or {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        for attempt in range(3):
            try:
                resp = await client.get(url, headers=h)
                if resp.status_code == 429:
                    logger.warning(f"HTTP 429 for {url} (attempt {attempt+1}/3)")
                    await asyncio.sleep((attempt + 1) * 5)
                    continue
                if resp.status_code == 200:
                    return resp.text
                logger.warning(f"HTTP {resp.status_code} for {url}")
                return None
            except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadTimeout) as e:
                logger.warning(f"HTTP connection error for {url}: {e} (attempt {attempt+1}/3)")
                if attempt < 2:
                    await asyncio.sleep((attempt + 1) * 3)
                    continue
                return None
            except Exception as e:
                logger.warning(f"HTTP unexpected error for {url}: {e}")
                return None
        return None

    async def _pw_page(self):
        browser = await _get_browser()
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        # Add stealth scripts to avoid bot detection
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'hi']});
        """)
        page = await context.new_page()
        page.set_default_timeout(self.timeout * 1000)
        return page, context

    async def _pw_goto(self, page, url: str) -> str | None:
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            await asyncio.sleep(2)
            return await page.content()
        except PWTimeout:
            try:
                return await page.content()
            except Exception as e2:
                logger.warning(f"PW goto timeout for {url}: {e2}")
                return None
        except Exception as e:
            logger.warning(f"PW goto failed for {url}: {e}")
            return None

    def _clean(self, text) -> str:
        if not text:
            return ""
        if hasattr(text, "get_text"):
            text = text.get_text()
        return re.sub(r"\s+", " ", str(text)).strip()

    def _extract_emails(self, text: str) -> list[str]:
        return list(set(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)))

    def _extract_phones(self, text: str) -> list[str]:
        phones = re.findall(r"(?:\+91|0)?[ -]?[6-9]\d{9}", text)
        cleaned = []
        for p in phones:
            digits = re.sub(r"[^\d]", "", p)
            if len(digits) >= 10:
                cleaned.append(digits[-10:] if len(digits) > 10 else digits)
        return cleaned

    def _guess_industry(self, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["bakery", "snack", "namkeen"]): return "Bakery"
        if any(w in q for w in ["hotel", "restaurant", "catering"]): return "Hotel"
        if any(w in q for w in ["wholesale", "wholesaler", "dealer"]): return "Wholesaler"
        if any(w in q for w in ["distributor", "distribution"]): return "Distributor"
        if any(w in q for w in ["manufacturer", "factory", "production"]): return "Food Manufacturer"
        if any(w in q for w in ["import", "exporter", "export"]): return "Importer/Exporter"
        if any(w in q for w in ["palm oil", "edible oil", "cooking oil", "vegetable oil", "sunflower oil", "mustard oil", "coconut oil"]): return "Edible Oil Trader"
        return "Food Processing Company"

    def crawl_job(self, query_string: str, source: str, target_city: str = "", target_state: str = ""):
        source_map = {
            "indiamart": self.crawl_indiamart,
            "justdial": self.crawl_justdial,
            "tradeindia": self.crawl_tradeindia,
            "exportersindia": self.crawl_exportersindia,
            "googlemaps": self.crawl_googlemaps,
            "google_maps": self.crawl_googlemaps,
            "company_website": self.crawl_company_website,
            "companywebsite": self.crawl_company_website,
            "yellowpages": self.crawl_yellowpages,
            "apeda": self.crawl_apeda,
            "gst_directory": self.crawl_gst_directory,
        }
        coro = source_map.get(source.lower())
        if not coro:
            logger.warning(f"No crawler for source '{source}' - falling back to tradeindia")
            coro = self.crawl_tradeindia
        return coro(query_string, target_city, target_state)

    # ─── TradeIndia (Playwright) ────────────────────────────────────────

    async def crawl_tradeindia(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            page, ctx = await self._pw_page()
            params = {"keyword": query}
            if city:
                params["city"] = city
            url = f"https://www.tradeindia.com/search.html?{urlencode(params)}"
            html = await self._pw_goto(page, url)
            if not html:
                logger.warning(f"TradeIndia: empty HTML for {url}")
                await ctx.close()
                return result

            soup = BeautifulSoup(html, "lxml")
            seen = set()
            profile_links: list[tuple[str, str]] = []

            cards = soup.select("div.card")
            if not cards:
                logger.warning(f"TradeIndia: no div.card found for {url} (html len={len(html)})")

            for card in cards:
                # Company profile link (ends with -digits/)
                comp_link = card.select_one("a[href*='tradeindia.com/'][href*='-']")
                comp_href = comp_link.get("href", "") if comp_link else ""
                if not re.search(r"-\d+/$", comp_href):
                    comp_link = None

                # Company name
                name_el = (
                    card.select_one("h3.coy-name") or
                    card.select_one("h3[class*='coy']")
                )
                if not name_el and comp_link:
                    name_el = comp_link
                if not name_el:
                    continue
                name = self._clean(name_el.get_text())
                # Strip "X Years" suffix if present
                name = re.sub(r"\s+\d+\s*Years$", "", name).strip()
                if not name or len(name) < 3:
                    continue
                if name.lower() in seen:
                    continue
                seen.add(name.lower())

                # Product title (for context, not stored as company)
                title_el = card.select_one("h2")
                _title = self._clean(title_el.get_text()) if title_el else ""

                # City / location
                loc_el = card.select_one("div.product_details span[class*='Body4R']")
                location_text = self._clean(loc_el.get_text()) if loc_el else ""
                # Remove the svg-related text noise; keep last token as city guess
                if location_text:
                    location_text = location_text.replace("Made in India", "").strip()

                # Business type
                business_type = ""
                for p in card.select("div.product_details p"):
                    pt = self._clean(p.get_text())
                    if pt.startswith("Business Type"):
                        business_type = pt.replace("Business Type:", "").strip()
                        break

                if comp_link:
                    profile_links.append((name, comp_href))

                result.companies.append(ExtractedCompany(
                    company_name=name,
                    address=location_text,
                    city=city or location_text.split()[-1] if location_text else city,
                    state=state,
                    source="tradeindia",
                    source_url=url,
                    confidence=60,
                    industry=self._guess_industry(query),
                    crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                ))

            # Second pass: visit company profile pages to extract contact details
            for cname, purl in profile_links[:5]:
                try:
                    html2 = await self._pw_goto(page, purl)
                    if not html2:
                        continue
                    soup2 = BeautifulSoup(html2, "lxml")
                    p_email, p_phone, p_website = "", "", ""

                    # Click "Show Contact" / "Email" / "View Number" buttons
                    try:
                        btns = await page.query_selector_all("button, a")
                        for btn in btns:
                            try:
                                txt = (await btn.inner_text()).lower()
                                if any(x in txt for x in ["show contact", "email", "get email", "view contact", "show number", "call now", "send inquiry"]):
                                    await btn.click()
                                    await asyncio.sleep(1)
                            except Exception:
                                continue
                    except Exception:
                        pass

                    fresh_html = await page.content()
                    soup2 = BeautifulSoup(fresh_html, "lxml")

                    for a_tag in soup2.find_all("a", href=True):
                        h = a_tag.get("href", "")
                        if h.startswith("mailto:"):
                            p_email = h.replace("mailto:", "").strip()
                            break
                    if not p_email:
                        for t in soup2.find_all(string=re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")):
                            p_email = t.strip()
                            break

                    for a_tag in soup2.find_all("a", href=True):
                        h = a_tag.get("href", "")
                        if h.startswith("tel:"):
                            digits = re.sub(r"[^\d]", "", h)
                            if len(digits) >= 10:
                                p_phone = digits
                                break

                    for a_tag in soup2.find_all("a", href=True):
                        h = a_tag.get("href", "")
                        if h.startswith("http") and "tradeindia.com" not in h:
                            p_website = h.rstrip("/")
                            break

                    for c in result.companies:
                        if c.company_name.lower() == cname.lower():
                            if p_email and not c.email:
                                c.email = p_email
                            if p_phone and not c.phone:
                                c.phone = p_phone
                            if p_website and not c.website:
                                c.website = p_website
                            break
                except Exception as e:
                    logger.warning(f"TradeIndia profile visit failed for {purl}: {e}")
                    continue

            result.pages_crawled = 1 if result.companies else 0
            logger.info(f"TradeIndia: {len(result.companies)} companies from {url}")
            await ctx.close()
        except Exception as e:
            logger.warning(f"TradeIndia crawl failed: {e}")
            result.errors.append(f"tradeindia: {e}")
        return result

    # ─── Google Maps (Playwright - works) ──────────────────────────────

    async def crawl_googlemaps(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            page, ctx = await self._pw_page()
            search_query = f"{query} in {city}" if city else query
            url = f"https://www.google.com/maps/search/{quote_plus(search_query)}"
            html = await self._pw_goto(page, url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for a in soup.select('a.hfpxzc'):
                    name = a.get('aria-label', '') or a.get_text(strip=True)
                    if not name or len(name) < 3:
                        continue
                    if name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    result.companies.append(ExtractedCompany(
                        company_name=name, city=city, state=state,
                        source="googlemaps", source_url=url, confidence=50,
                        industry=self._guess_industry(query),
                        crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                result.pages_crawled = 1 if result.companies else 0
            await ctx.close()
        except Exception as e:
            result.errors.append(f"googlemaps: {e}")
        return result

    # ─── IndiaMART (Playwright - rate limited, may fail) ───────────────

    async def crawl_indiamart(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        max_retries = 2
        for attempt in range(max_retries):
            try:
                browser = await _get_browser()
                context = await browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1366, "height": 768},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Encoding": "gzip, deflate, br",
                        "DNT": "1",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )
                # Add stealth scripts to avoid detection
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = { runtime: {} };
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en', 'hi']});
                """)
                page = await context.new_page()
                page.set_default_timeout(self.timeout * 1000)

                # Visit homepage first to get cookies
                try:
                    await page.goto("https://www.indiamart.com", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(random.uniform(3, 6))
                except Exception:
                    pass

                # Search URL with random delay between retries
                if attempt > 0:
                    await asyncio.sleep(random.uniform(5, 10))

                url = f"https://www.indiamart.com/search?q={quote_plus(query)}"
                try:
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
                    # Wait for content to load with random delay
                    await asyncio.sleep(random.uniform(4, 8))

                    # Check if we got blocked
                    html = await page.content()
                    if "429" in html or len(html) < 500:
                        logger.warning(f"IndiaMART blocked request for '{query}' (attempt {attempt + 1})")
                        await context.close()
                        if attempt < max_retries - 1:
                            continue  # Retry with longer delay
                        result.errors.append("indiamart: rate limited (429)")
                        return result

                    # Try to wait for search results
                    try:
                        await page.wait_for_selector(
                            "div.srch-rslt-itm, [class*='seller'], [class*='card'], h2 a",
                            timeout=8000,
                        )
                        await asyncio.sleep(2)
                        html = await page.content()
                    except Exception:
                        pass

                    soup = BeautifulSoup(html, "lxml")
                    seen = set()

                    # Primary selectors based on IndiaMART's actual HTML structure
                    cards = soup.select(
                        "div.srch-rslt-itm, "           # Main search result item
                        "div[class*='seller-info'], "    # Seller info card
                        "div[class*='card'], "            # Generic card
                        "div[class*='product-card'], "    # Product card
                        "div[class*='listing']"           # Listing card
                    )

                    for card in cards:
                        # Try multiple name selectors
                        name_el = (
                            card.select_one("h2 a") or
                            card.select_one("h3 a") or
                            card.select_one("[class*='name'] a") or
                            card.select_one("a[href*='supplier']") or
                            card.select_one("[class*='title']") or
                            card.select_one("h2") or
                            card.select_one("h3")
                        )
                        if not name_el:
                            continue
                        name = self._clean(name_el.get_text())
                        if not name or len(name) < 3 or name.lower() in seen:
                            continue
                        seen.add(name.lower())

                        # Extract website
                        website = ""
                        website_el = card.select_one("a[href*='http'][href*='.com'], a[href*='http'][href*='.in']")
                        if website_el:
                            href = website_el.get("href", "")
                            if "indiamart.com" not in href:
                                website = href

                        # Extract phone
                        phone = ""
                        phone_el = (
                            card.select_one("a[href^='tel:']") or
                            card.select_one("span[class*='phone']") or
                            card.select_one("[class*='mob']") or
                            card.select_one("span[class*='contact']")
                        )
                        if phone_el:
                            phone_text = phone_el.get_text() if phone_el.name != "a" else phone_el.get("href", "")
                            phone = re.sub(r"[^\d]", "", phone_text)
                            if len(phone) < 10:
                                phone = ""

                        # Extract email
                        email = ""
                        email_el = card.select_one("a[href^='mailto:']")
                        if email_el:
                            email = email_el.get("href", "").replace("mailto:", "")

                        # Extract location
                        location_text = ""
                        loc_el = (
                            card.select_one("[class*='loc']") or
                            card.select_one("span[class*='city']") or
                            card.select_one("[class*='address']")
                        )
                        if loc_el:
                            location_text = self._clean(loc_el.get_text())

                        result.companies.append(ExtractedCompany(
                            company_name=name,
                            website=website,
                            phone=phone,
                            email=email,
                            address=location_text,
                            city=city,
                            state=state,
                            source="indiamart",
                            source_url=url,
                            confidence=55,
                            industry=self._guess_industry(query),
                            crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                        ))

                    result.pages_crawled = 1 if result.companies else 0
                except Exception as e:
                    logger.debug(f"IndiaMART search failed for '{query}': {e}")

                await context.close()
                break  # Success or non-retryable error, exit loop
            except Exception as e:
                result.errors.append(f"indiamart: {e}")
                if attempt < max_retries - 1:
                    continue
        return result

    # ─── JustDial (Playwright - may be blocked) ────────────────────────

    async def crawl_justdial(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        if not city:
            city = "Mumbai"
        try:
            page, ctx = await self._pw_page()
            city_slug = city.lower().replace(" ", "-")
            q_slug = query.lower().replace(" ", "-")
            url = f"https://www.justdial.com/{city_slug}/{q_slug}"
            html = await self._pw_goto(page, url)
            if not html:
                # Fallback: use the search endpoint
                url = f"https://www.justdial.com/{city_slug}/search?q={quote_plus(query)}"
                html = await self._pw_goto(page, url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for listing in soup.select("div.resultbox_info, li.cntanr, div.feedrc, section.search-result, div[class*='result'], li[class*='cnt'], div.storelist"):
                    name = self._clean(listing.select_one("h2 a, span.resultbox_name, span[class*='name'], h3 a, a[class*='name']"))
                    if not name or len(name) < 3 or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    location = self._clean(listing.select_one("span.resultbox_address, span.locality, span[class*='address'], div[class*='addr']"))
                    phone_el = listing.select_one("span.mobilesv, span[class*='phone'], a[href^='tel:']")
                    phone = re.sub(r"[^\d]", "", phone_el.get_text()) if phone_el else ""
                    result.companies.append(ExtractedCompany(
                        company_name=name, phone=phone, address=location,
                        city=city, state=state, source="justdial",
                        source_url=url, confidence=55,
                        industry=self._guess_industry(query),
                        crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                result.pages_crawled = 1 if result.companies else 0
            await ctx.close()
        except Exception as e:
            result.errors.append(f"justdial: {e}")
        return result

    # ─── ExportersIndia (httpx) ─────────────────────────────────────────

    async def crawl_exportersindia(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            url = f"https://www.exportersindia.com/search?{urlencode({'q': query})}"
            html = await self._fetch(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    text = a.get_text(strip=True)
                    if not text or len(text) < 5:
                        continue
                    if any(p in href for p in ['/product/', '/company/', '/supplier/']):
                        if text.lower() in seen:
                            continue
                        seen.add(text.lower())
                        result.companies.append(ExtractedCompany(
                            company_name=text, city=city, state=state,
                            source="exportersindia", source_url=url, confidence=50,
                            industry=self._guess_industry(query),
                            crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                        ))
                result.pages_crawled = 1 if result.companies else 0
        except Exception as e:
            result.errors.append(f"exportersindia: {e}")
        return result

    # ─── YellowPages (httpx) ────────────────────────────────────────────

    async def crawl_yellowpages(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            url = f"https://www.yellowpages.co.in/search?search_terms={quote_plus(query)}&geo_location_terms={quote_plus(city) if city else 'India'}"
            html = await self._fetch(url)
            if not html:
                url = f"https://www.yellowpages.co.in/{city}/{query}".replace(" ", "-") if city else f"https://www.yellowpages.co.in/search?search_terms={quote_plus(query)}"
                html = await self._fetch(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for card in soup.select("div.result, div.search-result, div.business-card, div[class*='result'], div[class*='business'], div.listing, li.listing"):
                    name = self._clean(card.select_one("h2 a, a.business-name, span[class*='name'], a[class*='name'], h3 a"))
                    if not name or len(name) < 3 or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    phone = self._clean(card.select_one("div.phone, span[class*='phone'], a[href^='tel:']"))
                    location = self._clean(card.select_one("div.locality, div.street-address, span[class*='addr'], p[class*='addr']"))
                    website_el = card.select_one("a[href*='http']")
                    website = website_el.get("href", "") if website_el else ""
                    result.companies.append(ExtractedCompany(
                        company_name=name, website=website,
                        phone=re.sub(r"[^\d]", "", phone) if phone else "",
                        address=location, city=city, state=state,
                        source="yellowpages", source_url=url, confidence=50,
                        industry=self._guess_industry(query),
                        crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                result.pages_crawled = 1 if result.companies else 0
        except Exception as e:
            result.errors.append(f"yellowpages: {e}")
        return result

    # ─── APEDA (httpx) ──────────────────────────────────────────────────

    async def crawl_apeda(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            url = f"https://apeda.gov.in/apedawebsite/search.htm?q={quote_plus(query)}"
            html = await self._fetch(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for row in soup.select("table tr, div.result-item, li.search-result, div.search-result"):
                    name = self._clean(row.select_one("a, span.title, td a, strong"))
                    if not name or len(name) < 3 or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    location = self._clean(row.select_one("td:nth-child(2), span.address, td+td"))
                    result.companies.append(ExtractedCompany(
                        company_name=name, address=location,
                        city=city, state=state,
                        source="apeda", confidence=70, industry="Importer/Exporter",
                        crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                result.pages_crawled = 1 if result.companies else 0
        except Exception as e:
            result.errors.append(f"apeda: {e}")
        return result

    # ─── GST Directory (httpx) ──────────────────────────────────────────

    async def crawl_gst_directory(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            url = f"https://www.gst.gov.in/search?q={quote_plus(query)}"
            html = await self._fetch(url)
            if html:
                soup = BeautifulSoup(html, "lxml")
                seen = set()
                for row in soup.select("table tr, div.search-result, div.result-item"):
                    cells = row.select("td, div.col")
                    if len(cells) < 2:
                        continue
                    name = self._clean(cells[0])
                    if not name or len(name) < 3 or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    result.companies.append(ExtractedCompany(
                        company_name=name, city=city, state=state,
                        source="gst_directory", confidence=60,
                        industry=self._guess_industry(query),
                        crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                    ))
                result.pages_crawled = 1 if result.companies else 0
        except Exception as e:
            result.errors.append(f"gst_directory: {e}")
        return result

    # ─── Company Website (Google + direct, httpx) ───────────────────────

    async def crawl_company_website(self, query: str, city: str = "", state: str = "") -> CrawlResult:
        result = CrawlResult()
        try:
            page, ctx = await self._pw_page()
            search_url = f"https://www.google.com/search?q={quote_plus(f'{query} company {city}')}"
            html = await self._pw_goto(page, search_url)
            await ctx.close()
            if not html:
                return result
            soup = BeautifulSoup(html, "lxml")
            urls = set()
            for a in soup.select("a[href^='http']"):
                href = a.get("href", "")
                if "google.com" in href or "youtube.com" in href:
                    continue
                m = re.search(r"https?://[^&'\"]+", href)
                if m:
                    u = m.group(0).rstrip("/")
                    urls.add(u)
            for url in list(urls)[:5]:
                page_html = await self._fetch(url)
                if not page_html:
                    continue
                psoup = BeautifulSoup(page_html, "lxml")
                title = psoup.find("title")
                name = self._clean(title.get_text() if title else "")
                if not name:
                    continue
                name = name.split("|")[0].split("-")[0].strip()
                text = psoup.get_text(" ", strip=True)
                emails = self._extract_emails(text)
                phones = self._extract_phones(text)
                result.companies.append(ExtractedCompany(
                    company_name=name, website=url,
                    email=emails[0] if emails else "",
                    phone=phones[0] if phones else "",
                    city=city, state=state, source="company_website",
                    source_url=url, confidence=65,
                    industry=self._guess_industry(query),
                    crawl_timestamp=datetime.now(timezone.utc).isoformat(),
                ))
            result.pages_crawled = len(urls)
        except Exception as e:
            result.errors.append(f"company_website: {e}")
        return result

    # ─── Enrichment & Contact Discovery ─────────────────────────────────

    async def enrich_company_website(self, website_url: str) -> dict:
        from backend.services.website_enricher import WebsiteEnricher
        enricher = WebsiteEnricher()
        try:
            data = await enricher.enrich(website_url)
            return {
                "about_us": data.about_us, "products": data.products,
                "brands": data.brands, "company_description": data.company_description,
                "contact_page": data.contact_page, "emails": data.emails,
                "phones": data.phones, "address": data.address,
                "city": data.city, "state": data.state,
            }
        finally:
            await enricher.close()

    async def discover_contacts(self, website_url: str) -> list[ExtractedContact]:
        from backend.services.contact_discovery import ProcurementContactDiscovery
        discoverer = ProcurementContactDiscovery()
        try:
            raw = await discoverer.discover(website_url)
            return [
                ExtractedContact(
                    person_name=c.name, designation=c.designation,
                    email=c.email, phone=c.phone,
                    linkedin_url=c.linkedin_url,
                    source_url=c.source_url, confidence=c.confidence,
                ) for c in raw
            ]
        finally:
            await discoverer.close()
