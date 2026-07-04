from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class CrawlLog(Base):
    __tablename__ = "crawl_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spider_name: Mapped[str] = mapped_column(String(50), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime | None] = mapped_column(DateTime)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    companies_found: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text)  # JSON array
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
