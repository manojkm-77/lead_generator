import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Chennai", "Kolkata",
    "Hyderabad", "Pune", "Ahmedabad", "Surat", "Lucknow", "Jaipur",
    "Ludhiana", "Vadodara", "Rajkot", "Gurugram", "Gurgaon", "Indore",
    "Bhopal", "Chandigarh", "Nagpur", "Thane", "Nashik", "Agra",
    "Meerut", "Faridabad", "Ghaziabad", "Patna", "Srinagar", "Kanpur",
    "Kochi", "Visakhapatnam", "Vijayawada", "Madurai",
    "Coimbatore", "Thiruvananthapuram", "Guwahati",
    "Bhubaneswar", "Ranchi", "Raipur", "Jodhpur",
    "Amritsar", "Varanasi", "New Delhi", "Noida",
    "Mangalore", "Mysore", "Hubli", "Dehradun",
    "Panaji", "Siliguri", "Allahabad", "Prayagraj",
]
CITY_PAT = re.compile(
    r'^([A-Z][A-Za-z0-9&.\s-]+?),\s*(' + "|".join(re.escape(c) for c in INDIAN_CITIES) + r')(?:,\s*India)?$'
)
CITY_SET = set(c.lower() for c in INDIAN_CITIES)
MIN_NAME_LEN = 8


class TradeIndiaSpider(BaseSpider):
    """Crawl TradeIndia for edible oil buyers and food businesses."""

    name = "tradeindia"
    allowed_domains = ["tradeindia.com"]
    SOURCE_NAME = "tradeindia"
    INDUSTRY_HINT = "Food"

    SEARCH_URL = "https://www.tradeindia.com/search.html"

    QUERIES = [
        "edible oil buyer",
        "palm oil distributor",
        "cooking oil wholesaler",
        "sunflower oil supplier",
        "food manufacturer india",
        "bakery supplier",
    ]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        for query in queries:
            for page in range(1, self.max_pages + 1):
                params = {"keyword": query, "page": page}
                url = f"{self.SEARCH_URL}?{urlencode(params)}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_search,
                    meta={"query": query, "page": page},
                    errback=self.handle_error,
                )

    def parse_search(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta["query"]
        page = response.meta["page"]
        self.logger.info(f"[{self.name}] Search: '{query}' page {page}")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "lxml")
        seen = set()
        count = 0
        profile_urls = set()

        # Method 1: Match "CompanyName, City, India" text pattern in links
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if not text or len(text) < 8:
                continue
            href = a.get("href", "")
            m = CITY_PAT.match(text)
            if m:
                name = self.clean_text(m.group(1))
                city = m.group(2).strip()
                if not name or len(name) < MIN_NAME_LEN or name.lower() in seen:
                    continue
                name_lower = name.lower()
                if name_lower in CITY_SET or name_lower.rstrip(".") in CITY_SET:
                    continue
                skip_words = ["all india", "click here", "view more", "read more", "home", "contact"]
                if any(w in name_lower for w in skip_words):
                    continue
                seen.add(name_lower)
                yield self.make_item(
                    company_name=name,
                    city=city,
                    industry=self._guess_industry(query),
                )
                count += 1

            # Collect company profile links (pattern: /slug-id/)
            if re.search(r'-\d+/$', href) and "tradeindia.com" in href:
                profile_urls.add(href)

        if count < 3:
            # Method 2: Extract text from anchor tags with company/supplier links
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True)
                if not text or len(text) < MIN_NAME_LEN or len(text) > 120:
                    continue
                href = a.get("href", "")
                is_company = any(p in href.lower() for p in ["/company/", "/supplier/", "/seller/"])
                has_city = any(c.lower() in text.lower() for c in INDIAN_CITIES)
                if not (is_company or has_city):
                    continue
                if text.lower() in seen:
                    continue
                name = text.split(",")[0].strip()[:80]
                name_lower = name.lower()
                if name_lower in CITY_SET or any(w in name_lower for w in ["all india", "click here", "view more", "home"]):
                    continue
                seen.add(text.lower())
                yield self.make_item(
                    company_name=name,
                    industry=self._guess_industry(query),
                )
                count += 1

        # Follow company profile links to extract contact details
        for purl in list(profile_urls)[:5]:
            yield scrapy.Request(
                purl,
                callback=self.parse_company,
                meta={"query": query},
                errback=self.handle_error,
            )

        self.logger.info(f"[{self.name}] Extracted {count} companies, following {len(profile_urls)} profiles")

    def parse_company(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta.get("query", "")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "lxml")
        h1 = soup.find("h1")
        name = self.clean_text(h1.get_text(strip=True)) if h1 else None
        if not name:
            return

        phones = self.extract_phones(response)
        emails = self.extract_emails(response)
        yield self.make_item(
            company_name=name,
            website=self.extract_website(response),
            phone=phones[0] if phones else None,
            email=emails[0] if emails else None,
            industry=self._guess_industry(query),
        )

    def _guess_industry(self, query):
        q = query.lower()
        if "bakery" in q:
            return "Bakery"
        if "wholesale" in q or "wholesaler" in q:
            return "Wholesaler"
        if "distributor" in q:
            return "Distributor"
        if "manufacturer" in q:
            return "Food Manufacturer"
        if "import" in q:
            return "Importer"
        return "Food Processing Company"
