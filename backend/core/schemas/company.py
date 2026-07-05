"""
BuyerHunter V2 — Company Schemas

Pydantic models for API request/response and internal data transfer.
Separates write (create/update) from read (response) schemas.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CompanyCreate(BaseModel):
    """Payload for creating a new company record."""
    canonical_name: str
    legal_name: str | None = None
    website_url: str | None = None
    gst_number: str | None = None
    cin_number: str | None = None
    iec_code: str | None = None
    fssai_number: str | None = None
    pan_number: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    legal_status: str = "unknown"
    company_tier: str = "unknown"
    is_manufacturer: bool = False
    is_importer: bool = False
    is_exporter: bool = False
    is_distributor: bool = False
    is_wholesaler: bool = False
    is_retailer: bool = False
    hq_country: str = "IN"
    hq_state: str | None = None
    hq_city: str | None = None
    hq_district: str | None = None
    hq_pincode: str | None = None
    hq_address: str | None = None
    factory_address: str | None = None
    warehouse_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    google_place_id: str | None = None
    linkedin_slug: str | None = None
    first_seen_source: str | None = None


class CompanyUpdate(BaseModel):
    """Partial update payload for a company."""
    canonical_name: str | None = None
    legal_name: str | None = None
    website_url: str | None = None
    gst_number: str | None = None
    cin_number: str | None = None
    iec_code: str | None = None
    fssai_number: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    legal_status: str | None = None
    company_tier: str | None = None
    confidence: int | None = None
    buyer_score: int | None = None
    tier: str | None = None
    is_manufacturer: bool | None = None
    is_importer: bool | None = None
    is_exporter: bool | None = None
    is_distributor: bool | None = None
    is_wholesaler: bool | None = None
    is_retailer: bool | None = None
    hq_state: str | None = None
    hq_city: str | None = None
    hq_district: str | None = None
    hq_address: str | None = None


class CompanyRead(BaseModel):
    """Full company record for API responses."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    legal_name: str | None = None
    website_url: str | None = None
    gst_number: str | None = None
    cin_number: str | None = None
    iec_code: str | None = None
    fssai_number: str | None = None
    industry: str | None = None
    sub_industry: str | None = None
    legal_status: str
    company_tier: str
    confidence: int
    buyer_score: int
    tier: str
    is_manufacturer: bool
    is_importer: bool
    is_exporter: bool
    is_distributor: bool
    is_wholesaler: bool
    is_retailer: bool
    hq_country: str
    hq_state: str | None = None
    hq_city: str | None = None
    hq_district: str | None = None
    hq_pincode: str | None = None
    hq_address: str | None = None
    factory_address: str | None = None
    warehouse_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    first_seen_source: str | None = None
    first_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class CompanyListItem(BaseModel):
    """Lightweight company record for list views."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    canonical_name: str
    website_url: str | None = None
    industry: str | None = None
    hq_state: str | None = None
    hq_city: str | None = None
    buyer_score: int
    confidence: int
    is_manufacturer: bool
    is_importer: bool
    created_at: datetime
