"""
BuyerHunter V2 — Search Job Schemas
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SearchJobCreate(BaseModel):
    """Payload for creating a search job."""
    query_string: str
    source: str
    priority: str = "normal"
    max_pages: int = 5
    target_state: str | None = None
    target_city: str | None = None
    target_country: str = "IN"
    parent_job_id: int | None = None
    run_id: str | None = None


class SearchJobRead(BaseModel):
    """Full search job record."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    query_string: str
    query_hash: str | None = None
    source: str
    source_url: str | None = None
    status: str
    priority: str
    retry_count: int
    max_retries: int
    max_pages: int
    pages_crawled: int
    companies_found: int
    contacts_found: int
    errors: dict | None = None
    target_state: str | None = None
    target_city: str | None = None
    target_country: str
    parent_job_id: int | None = None
    run_id: str | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
