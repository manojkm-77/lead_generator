"""
BuyerHunter V2 — Contact Model

Type-classified contact lines. One row per channel per person.
Supports: email, phone, whatsapp, linkedin.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Enum, ForeignKey, Index, Integer, SmallInteger, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import V2Base


class ContactChannel(str, enum.Enum):
    EMAIL = "email"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    WEBSITE_FORM = "website_form"


class ContactPurpose(str, enum.Enum):
    OFFICIAL = "official"
    SALES = "sales"
    PROCUREMENT = "procurement"
    SUPPORT = "support"
    GENERAL = "general"
    UNKNOWN = "unknown"


class Contact(V2Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    # Person info
    person_name: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(Text)
    department: Mapped[str | None] = mapped_column(Text)

    # Contact channel (one row per channel per person)
    channel: Mapped[ContactChannel] = mapped_column(
        Enum(ContactChannel, native_enum=False), nullable=False
    )
    channel_value: Mapped[str] = mapped_column(Text, nullable=False)
    channel_purpose: Mapped[ContactPurpose] = mapped_column(
        Enum(ContactPurpose, native_enum=False), default=ContactPurpose.GENERAL
    )

    # Quality
    confidence: Mapped[int] = mapped_column(SmallInteger, default=50)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column()

    # Provenance
    source_crawl_job_id: Mapped[int | None] = mapped_column(Integer)
    evidence_ledger_id: Mapped[int | None] = mapped_column(Integer)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    company = relationship("Company", back_populates="contacts")

    __table_args__ = (
        Index("idx_contacts_company", company_id),
        Index("idx_contacts_channel", channel),
        Index("idx_contacts_confidence", confidence.desc()),
        UniqueConstraint(
            company_id, channel, "channel_value",
            name="uq_contacts_company_channel_value",
        ),
    )
