from datetime import datetime
from pydantic import BaseModel


class CompanyCreate(BaseModel):
    company_name: str
    website: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str = "India"
    gst_number: str | None = None
    industry: str | None = None
    products: str | None = None
    lead_score: int = 0
    source: str | None = None
    business_type: str | None = None
    is_importer: bool = False
    is_exporter: bool = False
    is_manufacturer: bool = False
    is_distributor: bool = False
    is_wholesaler: bool = False
    is_retailer: bool = False
    cin_number: str | None = None
    iec_code: str | None = None
    employees: int | None = None
    turnover: str | None = None
    founded_year: int | None = None
    linkedin_url: str | None = None


class CompanyRead(CompanyCreate):
    id: int
    ai_reason: str | None = None
    ai_confidence: int = 0
    ai_consumption: str | None = None
    ai_frequency: str | None = None
    about_us: str | None = None
    brands: str | None = None
    industries_served: str | None = None
    company_description: str | None = None
    contact_page: str | None = None
    careers_page: str | None = None
    procurement_info: str | None = None
    estimated_size: str | None = None
    potential_oil_usage: str | None = None
    estimated_annual_consumption: str | None = None
    enriched_at: datetime | None = None
    crawl_date: datetime
    created_at: datetime
    updated_at: datetime
    # Geolocation
    latitude: float | None = None
    longitude: float | None = None
    # Business
    import_status: str | None = None
    export_status: str | None = None
    revenue: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    youtube_url: str | None = None
    google_rating: float | None = None
    # Addresses
    factory_address: str | None = None
    office_address: str | None = None
    warehouse_address: str | None = None
    district: str | None = None
    # Contacts
    official_email: str | None = None
    sales_email: str | None = None
    support_email: str | None = None
    official_phone: str | None = None
    whatsapp_business: str | None = None
    # Certifications
    fssai_number: str | None = None
    apeda_registration: str | None = None
    iso_certification: str | None = None
    haccp_certification: str | None = None
    brc_certification: str | None = None
    # Trade
    export_markets: str | None = None
    import_countries: str | None = None
    # Scoring
    buyer_score: int = 0
    confidence: int = 0
    lead_status: str | None = None
    opportunity_score: int = 0
    risk_score: int = 0
    is_verified: bool = False
    last_updated: datetime | None = None

    model_config = {"from_attributes": True}


class CompanyList(BaseModel):
    total: int
    page: int
    page_size: int
    companies: list[CompanyRead]
