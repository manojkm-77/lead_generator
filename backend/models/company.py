from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(20), index=True)
    whatsapp: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100), index=True)
    state: Mapped[str | None] = mapped_column(String(100), index=True)
    country: Mapped[str] = mapped_column(String(50), default="India")
    gst_number: Mapped[str | None] = mapped_column(String(15), unique=True)
    industry: Mapped[str | None] = mapped_column(String(100), index=True)
    products: Mapped[str | None] = mapped_column(Text)
    lead_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    ai_reason: Mapped[str | None] = mapped_column(Text)
    ai_confidence: Mapped[int] = mapped_column(Integer, default=0)
    ai_consumption: Mapped[str | None] = mapped_column(String(50))
    ai_frequency: Mapped[str | None] = mapped_column(String(50))
    about_us: Mapped[str | None] = mapped_column(Text)
    brands: Mapped[str | None] = mapped_column(Text)
    industries_served: Mapped[str | None] = mapped_column(Text)
    company_description: Mapped[str | None] = mapped_column(Text)
    contact_page: Mapped[str | None] = mapped_column(String(500))
    careers_page: Mapped[str | None] = mapped_column(String(500))
    procurement_info: Mapped[str | None] = mapped_column(Text)
    estimated_size: Mapped[str | None] = mapped_column(String(50))
    potential_oil_usage: Mapped[str | None] = mapped_column(String(50))
    estimated_annual_consumption: Mapped[str | None] = mapped_column(String(100))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str | None] = mapped_column(String(50), index=True)
    crawl_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Geolocation
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # Business classification
    business_type: Mapped[str | None] = mapped_column(String(50))
    is_importer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_exporter: Mapped[bool] = mapped_column(Boolean, default=False)
    is_manufacturer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_distributor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_wholesaler: Mapped[bool] = mapped_column(Boolean, default=False)
    is_retailer: Mapped[bool] = mapped_column(Boolean, default=False)
    import_status: Mapped[str | None] = mapped_column(String(50))
    export_status: Mapped[str | None] = mapped_column(String(50))

    # Company details
    cin_number: Mapped[str | None] = mapped_column(String(21))
    iec_code: Mapped[str | None] = mapped_column(String(10))
    employees: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[str | None] = mapped_column(String(100))
    turnover: Mapped[str | None] = mapped_column(String(100))
    founded_year: Mapped[int | None] = mapped_column(Integer)
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    facebook_url: Mapped[str | None] = mapped_column(String(500))
    instagram_url: Mapped[str | None] = mapped_column(String(500))
    youtube_url: Mapped[str | None] = mapped_column(String(500))
    google_rating: Mapped[float | None] = mapped_column(Float)

    # Multiple addresses
    factory_address: Mapped[str | None] = mapped_column(Text)
    office_address: Mapped[str | None] = mapped_column(Text)
    warehouse_address: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(String(100))

    # Multiple contacts
    official_email: Mapped[str | None] = mapped_column(String(255))
    sales_email: Mapped[str | None] = mapped_column(String(255))
    procurement_email: Mapped[str | None] = mapped_column(String(255))
    support_email: Mapped[str | None] = mapped_column(String(255))
    official_phone: Mapped[str | None] = mapped_column(String(20))
    whatsapp_business: Mapped[str | None] = mapped_column(String(20))
    pin_code: Mapped[str | None] = mapped_column(String(10))

    # Certifications
    fssai_number: Mapped[str | None] = mapped_column(String(50))
    apeda_registration: Mapped[str | None] = mapped_column(String(50))
    iso_certification: Mapped[str | None] = mapped_column(String(50))
    haccp_certification: Mapped[str | None] = mapped_column(String(50))
    brc_certification: Mapped[str | None] = mapped_column(String(50))

    # Trade
    export_markets: Mapped[str | None] = mapped_column(Text)
    import_countries: Mapped[str | None] = mapped_column(Text)

    # Scoring
    buyer_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    lead_status: Mapped[str | None] = mapped_column(String(20), index=True)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
