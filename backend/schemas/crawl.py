from datetime import datetime
from pydantic import BaseModel


class CrawlRequest(BaseModel):
    spider_name: str
    keywords: list[str] = []
    max_pages: int = 10


class CrawlLogRead(BaseModel):
    id: int
    spider_name: str
    start_time: datetime
    end_time: datetime | None
    pages_crawled: int
    companies_found: int
    duplicates_removed: int
    errors: str | None
    status: str

    model_config = {"from_attributes": True}
