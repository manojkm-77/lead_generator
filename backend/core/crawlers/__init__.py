from backend.core.crawlers.base import BaseCrawlerAdapter, CrawlResult, CrawledEntity
from backend.core.crawlers.indiamart import IndiaMARTAdapter
from backend.core.crawlers.tradeindia import TradeIndiaAdapter
from backend.core.crawlers.justdial import JustdialAdapter
from backend.core.crawlers.googlemaps import GoogleMapsAdapter
from backend.core.crawlers.fssai import FSSAIAdapter
from backend.core.crawlers.generic_website import GenericCorporateWebsiteAdapter

ALL_ADAPTERS = [
    IndiaMARTAdapter,
    TradeIndiaAdapter,
    JustdialAdapter,
    GoogleMapsAdapter,
    FSSAIAdapter,
    GenericCorporateWebsiteAdapter,
]

__all__ = [
    "BaseCrawlerAdapter", "CrawlResult", "CrawledEntity",
    "IndiaMARTAdapter", "TradeIndiaAdapter", "JustdialAdapter",
    "GoogleMapsAdapter", "FSSAIAdapter", "GenericCorporateWebsiteAdapter",
    "ALL_ADAPTERS",
]
