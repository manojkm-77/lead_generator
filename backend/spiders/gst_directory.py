import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class GSTDirectorySpider(BaseSpider):
    """Crawl public GST directory for registered food businesses.

    Uses the public GST portal search to find businesses
    registered under food and edible oil categories.
    """

    name = "gst_directory"
    SOURCE_NAME = "gst_directory"
    INDUSTRY_HINT = "Food"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    SEARCH_URL = "https://services.gst.gov.in/services/searchtp"

    QUERIES = [
        "edible oil",
        "palm oil",
        "cooking oil",
        "food manufacturer",
        "bakery products",
        "snack food",
    ]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        for query in queries:
            yield scrapy.Request(
                self.SEARCH_URL,
                callback=self.parse_search_form,
                meta={"query": query, "playwright": True},
                errback=self.handle_error,
            )

    def parse_search_form(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta["query"]

        # Extract GST numbers from search results if available
        gst_rows = response.css("table tr, div.result-item")
        for row in gst_rows:
            item = self._extract_gst_record(row)
            if item:
                yield item

    def parse_gst_detail(self, response):
        self.stats["pages_crawled"] += 1

        name = self.clean_text(
            response.css("tr:contains('Legal Name') td:last-child::text").get()
            or response.css("h1::text").get()
        )
        if not name:
            return

        gst = self.clean_text(
            response.css("tr:contains('GSTIN') td:last-child::text").get()
        )

        address = self.clean_text(
            response.css("tr:contains('Address') td:last-child::text").get()
            or response.css("div.address::text").get()
        )
        city, state = self.extract_location(address)

        # Try to extract state from GST number (first 2 digits)
        if gst and not state and len(gst) >= 2:
            state_code = gst[:2]
            state_map = {
                "27": "Maharashtra", "07": "Delhi", "19": "West Bengal",
                "24": "Gujarat", "33": "Tamil Nadu", "36": "Telangana",
                "29": "Karnataka", "09": "Uttar Pradesh", "08": "Rajasthan",
                "23": "Madhya Pradesh", "06": "Haryana", "04": "Goa",
            }
            state = state_map.get(state_code)

        industry_text = self.clean_text(
            response.css("tr:contains('Nature of Business') td:last-child::text").get()
        )
        industry = self._classify_industry(industry_text or "")

        yield self.make_item(
            company_name=name,
            gst_number=gst,
            address=address,
            city=city,
            state=state,
            industry=industry,
        )

    def _extract_gst_record(self, row):
        name = self.clean_text(row.css("td:first-child a::text, td:first-child::text").get())
        if not name or len(name) < 3:
            return None

        gst = self.clean_text(row.css("td:nth-child(2)::text").get())
        location = self.clean_text(row.css("td:last-child::text").get())
        city, state = self.extract_location(location)

        detail_link = row.css("td:first-child a::attr(href)").get()

        item = self.make_item(
            company_name=name,
            gst_number=gst,
            city=city,
            state=state,
            industry="Food Manufacturer",
        )

        if detail_link:
            yield scrapy.Request(
                urljoin(self.SEARCH_URL, detail_link),
                callback=self.parse_gst_detail,
                errback=self.handle_error,
                priority=5,
            )

        return item

    def _classify_industry(self, text):
        text = text.lower()
        if any(w in text for w in ["manufacturing", "manufacturer"]):
            return "Food Manufacturer"
        if any(w in text for w in ["trading", "trader", "wholesale"]):
            return "Wholesaler"
        if any(w in text for w in ["service", "restaurant", "hotel"]):
            return "Restaurant"
        if any(w in text for w in ["retail"]):
            return "Retail Chain"
        return "Food Processing Company"
