import re
import json
import logging
from datetime import datetime, timezone

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class GoogleMapsSpider(BaseSpider):
    """Crawl Google Maps for edible oil businesses.

    Uses Google Maps search results to find food businesses.
    Requires Playwright for JavaScript rendering.
    """

    name = "googlemaps"
    SOURCE_NAME = "googlemaps"
    INDUSTRY_HINT = "Food"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 5,
        "CONCURRENT_REQUESTS": 2,
    }

    QUERIES = [
        "edible oil dealer near me",
        "cooking oil wholesaler",
        "palm oil distributor",
        "food manufacturer",
        "bakery supplier",
        "snack manufacturer",
    ]

    CITIES = ["Mumbai", "Delhi", "Bangalore"]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        cities = self.CITIES[:2]

        for city in cities:
            for query in queries:
                search_query = f"{query} in {city}"
                url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
                yield scrapy.Request(
                    url,
                    callback=self.parse_maps,
                    meta={"city": city, "query": query, "playwright": True},
                    errback=self.handle_error,
                )

    def parse_maps(self, response):
        self.stats["pages_crawled"] += 1
        city = response.meta["city"]
        query = response.meta["query"]

        self.logger.info(f"[{self.name}] Parsing maps: {query} in {city}")

        # Extract business cards from Google Maps results
        results = response.css("div.Nv2PK, div[jsaction*='mouseover']")
        for result in results:
            item = self._extract_business(result, city, query)
            if item:
                yield item

        # Try to click "more results" if available
        more_btn = response.css("button:contains('More'), a:contains('Next')")
        if more_btn:
            yield scrapy.Request(
                response.url,
                callback=self.parse_maps,
                meta={"city": city, "query": query, "playwright": True},
                errback=self.handle_error,
                priority=-1,
            )

    def _extract_business(self, result, city, query):
        name = self.clean_text(
            result.css("div.qBF1Pd::text, span.fontHeadlineSmall::text").get()
        )
        if not name:
            return None

        rating = result.css("span.MW4etd::text").get()
        reviews = result.css("span.UY7F9::text").get()

        # Try to get address from the result
        address = self.clean_text(
            result.css("div.W4Efsd span:last-child::text").get()
        )
        parsed_city, state = self.extract_location(address) if address else (city, None)

        # Phone might be in the detail page
        phone = None
        phone_text = result.css("span[data-item-id*='phone']::text").get()
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text)
            if len(digits) >= 10:
                phone = digits

        website = None
        link = result.css("a[data-item-id*='website']::attr(href)").get()
        if link:
            website = link

        return self.make_item(
            company_name=name,
            website=website,
            phone=phone,
            city=parsed_city or city,
            state=state,
            industry=self._guess_industry(query),
        )

    def _guess_industry(self, query):
        q = query.lower()
        if "bakery" in q:
            return "Bakery"
        if "snack" in q or "namkeen" in q:
            return "Food Manufacturer"
        if "wholesale" in q or "wholesaler" in q:
            return "Wholesaler"
        if "distributor" in q:
            return "Distributor"
        if "manufacturer" in q:
            return "Food Manufacturer"
        return "Food Processing Company"
