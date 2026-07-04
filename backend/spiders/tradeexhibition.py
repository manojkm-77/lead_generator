import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class TradeExhibitionSpider(BaseSpider):
    """Crawl trade exhibition exhibitor lists for food industry businesses.

    Targets public exhibitor directories from food and beverage expos.
    """

    name = "tradeexhibition"
    SOURCE_NAME = "tradeexhibition"
    INDUSTRY_HINT = "Food Industry"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 3,
    }

    # Public exhibition exhibitor pages
    EXHIBITION_URLS = [
        # Food & beverage expos
        "https://www.indiafoodexpo.in/exhibitors",
        "https://www.aaharexpo.com/exhibitor-directory",
        "https://www.foodprocessing.in/exhibitors",
        "https://www.packfoodexpo.com/exhibitors",
        # Regional food expos
        "https://www.sialindia.com/exhibitor-list",
        "https://www.anuga.com/exhibitors",
    ]

    def start_requests(self):
        urls = self.urls if self.urls else self.EXHIBITION_URLS[:4]
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_exhibition,
                errback=self.handle_error,
                meta={"playwright": True},
            )

    def parse_exhibition(self, response):
        self.stats["pages_crawled"] += 1
        self.logger.info(f"[{self.name}] Parsing exhibition: {response.url}")

        exhibitor_cards = (
            response.css("div.exhibitor-card, div.exhibitor-item")
            or response.css("li.exhibitor, div.company-card")
            or response.css("div.card, tr.exhibitor-row")
        )

        for card in exhibitor_cards:
            item = self._extract_exhibitor(card)
            if item:
                yield item

        # Follow exhibitor detail links
        detail_links = response.css(
            "a[href*='exhibitor']::attr(href), a[href*='company']::attr(href)"
        ).getall()
        for link in detail_links[:20]:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_exhibitor_detail,
                errback=self.handle_error,
                priority=5,
            )

        # Pagination
        next_links = response.css(
            "a.next::attr(href), a:contains('Next')::attr(href), li.next a::attr(href)"
        ).getall()
        for link in next_links[:2]:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_exhibition,
                errback=self.handle_error,
                priority=1,
            )

    def parse_exhibitor_detail(self, response):
        self.stats["pages_crawled"] += 1

        name = self.clean_text(
            response.css("h1::text, h2.exhibitor-name::text, div.company-name::text").get()
        )
        if not name:
            return

        phones = self.extract_phones(response)
        emails = self.extract_emails(response)

        address = self.clean_text(
            response.css("[itemprop='address']::text, div.address::text, span.location::text").get()
        )
        city, state = self.extract_location(address)

        # Extract stand/booth number for context
        stand = self.clean_text(
            response.css("span.stand::text, div.booth::text, td:contains('Stand') + td::text").get()
        )

        products = response.css(
            "span.product::text, li.product-tag::text, div.product-category::text"
        ).getall()

        website = None
        links = response.css("a[href^='http']::attr(href)").getall()
        for link in links:
            if "exhibition" not in link and "expo" not in link:
                website = link
                break

        yield self.make_item(
            company_name=name,
            website=website,
            phone=phones[0] if phones else None,
            whatsapp=phones[0] if phones else None,
            email=emails[0] if emails else None,
            address=address,
            city=city,
            state=state,
            products=json.dumps([self.clean_text(p) for p in products[:5] if self.clean_text(p)]) if products else None,
            industry="Food Manufacturer",
        )

    def _extract_exhibitor(self, card):
        name = self.clean_text(
            card.css("h3 a::text, h4::text, span.name::text, a.exhibitor-name::text").get()
        )
        if not name or len(name) < 3:
            return None

        location = self.clean_text(
            card.css("span.location::text, span.city::text, div.address::text").get()
        )
        city, state = self.extract_location(location)

        phone_text = card.css("span.phone::text, a[href^='tel:']::attr(href)").get()
        phone = None
        if phone_text:
            digits = re.sub(r"[^\d]", "", phone_text.replace("tel:", ""))
            if len(digits) >= 10:
                phone = digits

        email_text = card.css("a[href^='mailto:']::attr(href)").get()
        email = email_text.replace("mailto:", "").strip().lower() if email_text else None

        website = card.css("a.website::attr(href), a[href^='http']:not([href*='exhibition'])::attr(href)").get()

        return self.make_item(
            company_name=name,
            website=website,
            phone=phone,
            email=email,
            city=city,
            state=state,
            industry="Food Manufacturer",
        )
