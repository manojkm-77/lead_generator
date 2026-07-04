import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class LinkedInCompanySpider(BaseSpider):
    """Crawl LinkedIn public company pages for food industry businesses.

    Only extracts publicly available information from company pages.
    Does not require login.
    """

    name = "linkedin"
    SOURCE_NAME = "linkedin"
    INDUSTRY_HINT = "Food Industry"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 5,
        "CONCURRENT_REQUESTS": 2,
    }

    QUERIES = [
        "edible oil company india",
        "food manufacturer india",
        "palm oil distributor",
        "cooking oil company",
        "bakery india",
    ]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:2]
        for query in queries:
            url = f"https://www.linkedin.com/companies/search?keywords={query.replace(' ', '%20')}"
            yield scrapy.Request(
                url,
                callback=self.parse_search,
                meta={"query": query, "playwright": True},
                errback=self.handle_error,
            )

    def parse_search(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta["query"]

        self.logger.info(f"[{self.name}] Search: '{query}'")

        # Extract company cards from search results
        cards = response.css("li.reusable-search__result-container, div.entity-result")
        for card in cards:
            item = self._extract_company_card(card)
            if item:
                yield item

        # Follow company page links
        links = response.css("a[href*='/company/']::attr(href)").getall()
        for link in links[:10]:
            if "/company/" in link:
                full_url = f"https://www.linkedin.com{link}" if not link.startswith("http") else link
                yield scrapy.Request(
                    full_url,
                    callback=self.parse_company_page,
                    meta={"query": query},
                    errback=self.handle_error,
                    priority=5,
                )

    def parse_company_page(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta.get("query", "")

        name = self.clean_text(
            response.css("h1.org-top-card-summary__title::text").get()
            or response.css("h1::text").get()
        )
        if not name:
            return

        industry = self.clean_text(
            response.css("dd.org-top-card-summary__industry::text").get()
            or response.css("span.company-industry::text").get()
        )

        location = self.clean_text(
            response.css("dd.org-top-card-summary__headquarter::text").get()
            or response.css("span.company-location::text").get()
        )
        city, state = self.extract_location(location)

        description = self.clean_text(
            response.css("p.org-about-organization__description::text").get()
            or response.css("section.about p::text").get()
        )

        # Classify based on description
        category = self._classify_from_text(f"{name} {industry} {description or ''}")

        website = None
        website_link = response.css("a[href*='redirect']:not([href*='linkedin'])::attr(href)").get()
        if website_link:
            website = website_link

        phone = None
        phone_text = response.css("span.org-top-card-summary__phone::text").get()
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text)
            if len(digits) >= 10:
                phone = digits

        yield self.make_item(
            company_name=name,
            website=website,
            phone=phone,
            city=city,
            state=state,
            industry=category or industry,
        )

    def _extract_company_card(self, card):
        name = self.clean_text(
            card.css("span.entity-result__title-text a::text").get()
        )
        if not name:
            return None

        industry = self.clean_text(
            card.css("div.entity-result__primary-subtitle::text").get()
        )

        location = self.clean_text(
            card.css("div.entity-result__secondary-subtitle::text").get()
        )
        city, state = self.extract_location(location)

        return self.make_item(
            company_name=name,
            city=city,
            state=state,
            industry=industry,
        )

    def _classify_from_text(self, text):
        text = text.lower()
        if any(w in text for w in ["bakery", "baker", "pastry", "bread"]):
            return "Bakery"
        if any(w in text for w in ["hotel", "resort", "hospitality"]):
            return "Hotel"
        if any(w in text for w in ["restaurant", "cafe", "food service"]):
            return "Restaurant"
        if any(w in text for w in ["distributor", "distribution"]):
            return "Distributor"
        if any(w in text for w in ["wholesale", "wholesaler"]):
            return "Wholesaler"
        if any(w in text for w in ["import", "importer"]):
            return "Importer"
        if any(w in text for w in ["export", "exporter"]):
            return "Exporter"
        if any(w in text for w in ["retail", "store", "supermarket"]):
            return "Retail Chain"
        if any(w in text for w in ["manufactur", "factory", "production", "processing"]):
            return "Food Manufacturer"
        return "Food Processing Company"
