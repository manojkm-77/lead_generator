"""
BuyerHunter V2 — Contact Schemas
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ContactCreate(BaseModel):
    """Payload for creating a contact line."""
    company_id: int
    person_name: str | None = None
    designation: str | None = None
    department: str | None = None
    channel: str  # email | phone | whatsapp | linkedin | website_form
    channel_value: str
    channel_purpose: str = "general"
    confidence: int = 50
    source_crawl_job_id: int | None = None
    evidence_ledger_id: int | None = None


class ContactRead(BaseModel):
    """Full contact record for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    person_name: str | None = None
    designation: str | None = None
    department: str | None = None
    channel: str
    channel_value: str
    channel_purpose: str
    confidence: int
    is_verified: bool
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
