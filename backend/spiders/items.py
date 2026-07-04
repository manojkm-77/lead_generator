import scrapy


class CompanyItem(scrapy.Item):
    company_name = scrapy.Field()
    website = scrapy.Field()
    phone = scrapy.Field()
    whatsapp = scrapy.Field()
    email = scrapy.Field()
    address = scrapy.Field()
    city = scrapy.Field()
    state = scrapy.Field()
    country = scrapy.Field(default="India")
    gst_number = scrapy.Field()
    industry = scrapy.Field()
    products = scrapy.Field()
    lead_score = scrapy.Field(default=0)
    source = scrapy.Field()
    crawl_date = scrapy.Field()
