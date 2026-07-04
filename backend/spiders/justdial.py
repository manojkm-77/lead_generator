import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class JustDialSpider(BaseSpider):
    """Crawl JustDial for edible oil buyers and food businesses."""

    name = "justdial"
    allowed_domains = ["justdial.com"]
    SOURCE_NAME = "justdial"
    INDUSTRY_HINT = "Food"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 4,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    SEARCH_URL = "https://www.justdial.com/{city}/{query}"

    CITIES = [
        "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
        "Kolkata", "Ahmedabad", "Pune", "Jaipur", "Lucknow",
    ]

    QUERIES = [
        "edible-oil-dealers",
        "cooking-oil-wholesalers",
        "palm-oil-distributors",
        "food-manufacturers",
        "bakery-suppliers",
        "snack-manufacturers",
    ]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        cities = ["Mumbai", "Delhi", "Bangalore"]

        for city in cities:
            for query in queries:
                url = self.SEARCH_URL.format(city=city, query=query)
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

        # Extract listings
        listings = response.css("div.resultbox_info")
        if not listings:
            listings = response.css("li.cntanr")
        if not listings:
            listings = response.css("div.feedrc")

        for listing in listings:
            item = self._extract_listing(listing, city, query)
            if item:
                yield item

        # Follow detail links
        detail_links = response.css("a.resultbox_name::attr(href)").getall()
        for link in detail_links[:15]:
            yield scrapy.Request(
                link,
                callback=self.parse_detail,
                meta={"city": city, "query": query},
                errback=self.handle_error,
                priority=5,
            )

        # Pagination
        if page < self.max_pages:
            next_url = urljoin(response.url, f"?page={page + 1}")
            yield scrapy.Request(
                next_url,
                callback=self.parse_search,
                meta={"city": city, "query": query, "page": page + 1},
                errback=self.handle_error,
                priority=1,
            )

    def parse_detail(self, response):
        self.stats["pages_crawled"] += 1
        city = response.meta.get("city")
        query = response.meta.get("query", "")

        name = self.clean_text(
            response.css("h1.fn::text").get()
            or response.css("span.shop_n::text").get()
            or response.css("h1::text").get()
        )
        if not name:
            return

        phones = self.extract_phones(response, "span.mobilesv::text, a[href^='tel:']::attr(href)")
        emails = self.extract_emails(response)

        address = self.clean_text(
            response.css("span.adrs::text").get()
            or response.css("span[itemprop='address']::text").get()
        )

        items_list = response.css("span.prdlist::text").getall()

        yield self.make_item(
            company_name=name,
            website=self.extract_website(response),
            phone=phones[0] if phones else None,
            whatsapp=phones[0] if phones else None,
            email=emails[0] if emails else None,
            address=address,
            city=city,
            state=None,
            products=json.dumps(items_list[:5]) if items_list else None,
            industry=self._guess_industry(query),
        )

    def _extract_listing(self, listing, city, query):
        name = self.clean_text(
            listing.css("h2 a::text, span.resultbox_name::text").get()
        )
        if not name:
            return None

        location = self.clean_text(
            listing.css("span.resultbox_address::text, span.locality::text").get()
        )
        parsed_city, state = self.extract_location(location) if location else (city, None)

        phone_text = listing.css("span.mobilesv::text").get()
        phone = None
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text)
            if len(digits) >= 10:
                phone = digits

        return self.make_item(
            company_name=name,
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
        if "wholesale" in q or "dealer" in q:
            return "Wholesaler"
        if "distributor" in q:
            return "Distributor"
        if "manufacturer" in q:
            return "Food Manufacturer"
        return "Food Processing Company"
