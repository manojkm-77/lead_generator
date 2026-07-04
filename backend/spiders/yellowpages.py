import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class YellowPagesSpider(BaseSpider):
    """Crawl Yellow Pages for edible oil buyers and food businesses."""

    name = "yellowpages"
    allowed_domains = ["yellowpages.co.in", "yellowpages.com"]
    SOURCE_NAME = "yellowpages"
    INDUSTRY_HINT = "Food"

    SEARCH_URL = "https://www.yellowpages.co.in/search"

    QUERIES = [
        "edible oil dealer",
        "cooking oil wholesaler",
        "palm oil distributor",
        "food manufacturer",
        "bakery supplier",
    ]

    CITIES = ["Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata"]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        cities = self.CITIES[:3]

        for city in cities:
            for query in queries:
                params = {"q": query, "loc": city}
                url = f"{self.SEARCH_URL}?{urlencode(params)}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_search,
                    meta={"city": city, "query": query, "page": 1},
                    errback=self.handle_error,
                )

    def parse_search(self, response):
        self.stats["pages_crawled"] += 1
        city = response.meta["city"]
        query = response.meta["query"]
        page = response.meta["page"]

        self.logger.info(f"[{self.name}] Search: {query} in {city} page {page}")

        listings = response.css("div.result, li.result, div.listing")
        for listing in listings:
            item = self._extract_listing(listing, city, query)
            if item:
                yield item

        # Pagination
        if page < self.max_pages:
            next_url = urljoin(response.url, f"&page={page + 1}")
            yield scrapy.Request(
                next_url,
                callback=self.parse_search,
                meta={"city": city, "query": query, "page": page + 1},
                errback=self.handle_error,
            )

    def _extract_listing(self, listing, city, query):
        name = self.clean_text(
            listing.css("h2 a::text, a.business-name::text, span.name::text").get()
        )
        if not name:
            return None

        location = self.clean_text(
            listing.css("div.address::text, span.locality::text").get()
        )
        parsed_city, state = self.extract_location(location) if location else (city, None)

        phone_text = listing.css("span.phone::text, a[href^='tel:']::attr(href)").get()
        phone = None
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text.replace("tel:", ""))
            if len(digits) >= 10:
                phone = digits

        email_text = listing.css("a[href^='mailto:']::attr(href)").get()
        email = email_text.replace("mailto:", "").strip().lower() if email_text else None

        website = listing.css("a.website::attr(href)").get()

        return self.make_item(
            company_name=name,
            website=website,
            phone=phone,
            email=email,
            city=parsed_city or city,
            state=state,
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
        return "Food Processing Company"
