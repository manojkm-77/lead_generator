import re
import json
import logging
from datetime import datetime, timezone

import scrapy
from backend.spiders.base import BaseSpider

logger = logging.getLogger(__name__)


class CompanyWebsiteSpider(BaseSpider):
    """Crawl individual company websites for business information."""

    name = "companywebsite"
    SOURCE_NAME = "companywebsite"
    INDUSTRY_HINT = None

    custom_settings = {
        **BaseSpider.custom_settings,
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 3,
    }

    def __init__(self, urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.urls = urls or []

    def start_requests(self):
        for url in self.urls:
            url = url.strip()
            if not url.startswith("http"):
                url = f"https://{url}"
            yield scrapy.Request(
                url,
                callback=self.parse_company,
                errback=self.handle_error,
                meta={"playwright": True},
                priority=10,
            )

    def parse_company(self, response):
        self.stats["pages_crawled"] += 1

        name = self.clean_text(
            response.css("h1::text").get()
            or response.css("title::text").get()
            or response.css("meta[property='og:site_name']::attr(content)").get()
        )
        if not name:
            return

        phones = self.extract_phones(response)
        emails = self.extract_emails(response)

        address = self.clean_text(
            response.css("[itemprop='address']::text").get()
            or response.css(".address::text").get()
            or response.css("footer .contact::text").get()
        )
        city, state = self.extract_location(address)

        # Try to find products/services
        products = []
        prod_selectors = [
            "div.product-name::text",
            "li.product::text",
            "div.service-item::text",
            "h3:contains('Product') + p::text",
            "h3:contains('Service') + p::text",
        ]
        for sel in prod_selectors:
            found = response.css(sel).getall()
            products.extend([self.clean_text(p) for p in found if self.clean_text(p)])
            if products:
                break

        # Try to find industry/category
        industry = None
        meta_desc = response.css("meta[name='description']::attr(content)").get("")
        og_desc = response.css("meta[property='og:description']::attr(content)").get("")
        desc_text = f"{meta_desc} {og_desc}".lower()

        industry_keywords = {
            "bakery": "Bakery",
            "hotel": "Hotel",
            "restaurant": "Restaurant",
            "manufacturer": "Food Manufacturer",
            "distributor": "Distributor",
            "wholesale": "Wholesaler",
            "retail": "Retail Chain",
            "import": "Importer",
            "export": "Exporter",
        }
        for keyword, cat in industry_keywords.items():
            if keyword in desc_text or keyword in name.lower():
                industry = cat
                break

        yield self.make_item(
            company_name=name,
            website=response.url,
            phone=phones[0] if phones else None,
            whatsapp=phones[0] if phones else None,
            email=emails[0] if emails else None,
            address=address,
            city=city,
            state=state,
            products=json.dumps(products[:5]) if products else None,
            industry=industry,
        )
