import re
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class TradeAssociationSpider(BaseSpider):
    """Crawl trade association member directories for food industry businesses.

    Targets:
    - FoodSafetyIndia.org member lists
    - AAHAR (Indian Food Expo) exhibitors
    - Industry association directories
    """

    name = "tradeassociation"
    SOURCE_NAME = "tradeassociation"
    INDUSTRY_HINT = "Food Industry"

    custom_settings = {
        **BaseSpider.custom_settings,
        "DOWNLOAD_DELAY": 3,
    }

    # Public association pages with member listings
    START_URLS = [
        # Food industry associations
        "https://www.foodsafetyindia.org/members",
        "https://www.aaharexpo.com/exhibitors",
        "https://www.indiafoodexpo.in/exhibitor-list",
        # Processed food associations
        "https://www.pfa.org.in/members",
        "https://www.ficci.in/food-sectors",
    ]

    def start_requests(self):
        urls = self.urls if self.urls else self.START_URLS
        for url in urls:
            yield scrapy.Request(
                url,
                callback=self.parse_directory,
                errback=self.handle_error,
                meta={"playwright": True},
            )

    def parse_directory(self, response):
        self.stats["pages_crawled"] += 1
        self.logger.info(f"[{self.name}] Parsing directory: {response.url}")

        # Try various member listing patterns
        member_cards = (
            response.css("div.member-card, div.exhibitor-card, li.member")
            or response.css("div.member, tr.member-row")
            or response.css("div.card, li.list-item")
        )

        for card in member_cards:
            item = self._extract_member(card)
            if item:
                yield item

        # Follow pagination
        next_links = response.css("a.next::attr(href), a:contains('Next')::attr(href)").getall()
        for link in next_links[:3]:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_directory,
                errback=self.handle_error,
                priority=1,
            )

        # Follow detail links
        detail_links = response.css("a[href*='member'], a[href*='exhibitor']::attr(href)").getall()
        for link in detail_links[:15]:
            yield scrapy.Request(
                urljoin(response.url, link),
                callback=self.parse_member_detail,
                errback=self.handle_error,
                priority=5,
            )

    def parse_member_detail(self, response):
        self.stats["pages_crawled"] += 1

        name = self.clean_text(
            response.css("h1::text, h2.member-name::text, div.company-name::text").get()
        )
        if not name:
            return

        phones = self.extract_phones(response)
        emails = self.extract_emails(response)

        address = self.clean_text(
            response.css("[itemprop='address']::text, div.address::text, span.location::text").get()
        )
        city, state = self.extract_location(address)

        products = response.css("li.product::text, span.product-tag::text").getall()

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
            industry="Food Manufacturer",
        )

    def _extract_member(self, card):
        name = self.clean_text(
            card.css("h3 a::text, h4::text, span.name::text, a.member-name::text").get()
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

        return self.make_item(
            company_name=name,
            phone=phone,
            email=email,
            city=city,
            state=state,
            industry="Food Manufacturer",
        )
