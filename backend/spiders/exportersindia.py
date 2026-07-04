import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class ExportersIndiaSpider(BaseSpider):
    """Crawl ExportersIndia for edible oil exporters and importers."""

    name = "exportersindia"
    allowed_domains = ["exportersindia.com"]
    SOURCE_NAME = "exportersindia"
    INDUSTRY_HINT = "Importer/Exporter"

    SEARCH_URL = "https://www.exportersindia.com/search"

    QUERIES = [
        "edible oil export",
        "palm oil importer",
        "cooking oil supplier",
        "food product exporter",
        "oil manufacturer",
    ]

    def start_requests(self):
        queries = self.queries if self.queries else self.QUERIES[:3]
        for query in queries:
            for page in range(1, self.max_pages + 1):
                params = {"q": query, "page": page}
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

        cards = response.css("div.result-item, div.listing-item, li.result")
        for card in cards:
            item = self._extract_card(card, query)
            if item:
                yield item

        links = response.css("a[href*='/company/']::attr(href)").getall()
        for link in links[:10]:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_company,
                meta={"query": query},
                errback=self.handle_error,
                priority=5,
            )

    def parse_company(self, response):
        self.stats["pages_crawled"] += 1
        query = response.meta.get("query", "")

        name = self.clean_text(
            response.css("h1.company_name::text, h1::text").get()
        )
        if not name:
            return

        phones = self.extract_phones(response)
        emails = self.extract_emails(response)

        address = self.clean_text(
            response.css("span.address::text, div.company-address::text").get()
        )
        city, state = self.extract_location(address)

        products = response.css("span.product-name::text, td:contains('Product') + td::text").getall()

        yield self.make_item(
            company_name=name,
            website=self.extract_website(response),
            phone=phones[0] if phones else None,
            whatsapp=phones[0] if phones else None,
            email=emails[0] if emails else None,
            address=address,
            city=city,
            state=state,
            products=json.dumps([self.clean_text(p) for p in products[:5] if self.clean_text(p)]) if products else None,
            industry="Importer" if "import" in query.lower() else "Exporter",
        )

    def _extract_card(self, card, query):
        name = self.clean_text(card.css("h3 a::text, h2::text, a.result-title::text").get())
        if not name:
            return None

        location = self.clean_text(card.css("span.location::text, span.city::text").get())
        city, state = self.extract_location(location)

        phone_text = card.css("span.phone::text").get()
        phone = None
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text)
            if len(digits) >= 10:
                phone = digits

        return self.make_item(
            company_name=name,
            phone=phone,
            city=city,
            state=state,
            industry="Importer" if "import" in query.lower() else "Exporter",
        )
