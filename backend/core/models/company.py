"""
BuyerHunter V2 — Company Model

Normalized for 10M+ rows. Contact data, evidence, and scoring
lives in separate tables. This is the canonical business entity.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Enum, Float, Index, Integer, SmallInteger, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import V2Base


class LegalStatus(str, enum.Enum):
    ACTIVE = "active"
    DISSOLVED = "dissolved"
    STRIKE_OFF = "strike_off"
    LIQUIDATION = "liquidation"
    DORMANT = "dormant"
    UNDER_INSOLVENCY = "under_insolvency"
    UNKNOWN = "unknown"


class CompanyTier(str, enum.Enum):
    ENTERPRISE = "enterprise"
    MID_MARKET = "mid_market"
    SMALL_BUSINESS = "small_business"
    MICRO = "micro"
    UNKNOWN = "unknown"


class Company(V2Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    legal_name: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)

    # Legal / registration
    gst_number: Mapped[str | None] = mapped_column(String(15))
    cin_number: Mapped[str | None] = mapped_column(String(21))
    iec_code: Mapped[str | None] = mapped_column(String(10))
    fssai_number: Mapped[str | None] = mapped_column(String(50))
    pan_number: Mapped[str | None] = mapped_column(String(10))

    # Classification
    industry: Mapped[str | None] = mapped_column(Text)
    sub_industry: Mapped[str | None] = mapped_column(Text)
    legal_status: Mapped[LegalStatus] = mapped_column(
        Enum(LegalStatus, native_enum=False), default=LegalStatus.UNKNOWN
    )
    company_tier: Mapped[CompanyTier] = mapped_column(
        Enum(CompanyTier, native_enum=False), default=CompanyTier.UNKNOWN
    )

    # Scoring
    confidence: Mapped[int] = mapped_column(SmallInteger, default=0)
    buyer_score: Mapped[int] = mapped_column(SmallInteger, default=0)
    tier: Mapped[CompanyTier] = mapped_column(
        Enum(CompanyTier, native_enum=False), default=CompanyTier.UNKNOWN
    )

    # Business type flags
    is_manufacturer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_importer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_exporter: Mapped[bool] = mapped_column(Boolean, default=False)
    is_distributor: Mapped[bool] = mapped_column(Boolean, default=False)
    is_wholesaler: Mapped[bool] = mapped_column(Boolean, default=False)
    is_retailer: Mapped[bool] = mapped_column(Boolean, default=False)

    # Physical presence
    hq_country: Mapped[str] = mapped_column(String(5), default="IN")
    hq_state: Mapped[str | None] = mapped_column(Text)
    hq_city: Mapped[str | None] = mapped_column(Text)
    hq_district: Mapped[str | None] = mapped_column(Text)
    hq_pincode: Mapped[str | None] = mapped_column(String(10))
    hq_address: Mapped[str | None] = mapped_column(Text)
    factory_address: Mapped[str | None] = mapped_column(Text)
    warehouse_address: Mapped[str | None] = mapped_column(Text)

    # Geolocation
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)

    # External identifiers
    google_place_id: Mapped[str | None] = mapped_column(Text)
    linkedin_slug: Mapped[str | None] = mapped_column(Text)

    # AI / enrichment metadata
    last_enriched_at: Mapped[datetime | None] = mapped_column()
    last_scored_at: Mapped[datetime | None] = mapped_column()

    # Provenance
    first_seen_source: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    contacts = relationship(
        "Contact", back_populates="company", cascade="all, delete-orphan",
        lazy="selectin",
    )
    evidence = relationship(
        "EvidenceLedger",
        primaryjoin="and_(EvidenceLedger.entity_type == 'company', "
                    "foreign(EvidenceLedger.entity_id) == Company.id)",
        back_populates="company",
        cascade="all, delete-orphan",
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_companies_buyer_score", buyer_score.desc()),
        Index("idx_companies_industry", industry),
        Index("idx_companies_state_city", hq_state, hq_city),
        Index("idx_companies_gst", gst_number, unique=True,
              postgresql_where="gst_number IS NOT NULL"),
    )
