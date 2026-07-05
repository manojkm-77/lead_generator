"""
BuyerHunter V2 — Evidence Ledger

Tracks exact provenance of every data point. Append-only.
Every field mutation on companies/contacts is recorded here with
full source attribution: URL, scraper method, timestamp, HTTP status.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Enum, Index, Integer, SmallInteger, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import V2Base


class EvidenceCategory(str, enum.Enum):
    SCRAPED_DIRECT = "scraped_direct"
    SCRAPED_RENDERED = "scraped_rendered"
    API_RESPONSE = "api_response"
    GOVERNMENT_REGISTRY = "government_registry"
    MANUAL_ENTRY = "manual_entry"
    AI_INFERRED = "ai_inferred"
    USER_SUBMITTED = "user_submitted"
    THIRD_PARTY = "third_party"


class EvidenceLedger(V2Base):
    __tablename__ = "evidence_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # What was mutated
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text)

    # Source provenance
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[str | None] = mapped_column(Text)
    source_method: Mapped[EvidenceCategory] = mapped_column(
        Enum(EvidenceCategory, native_enum=False),
        default=EvidenceCategory.SCRAPED_DIRECT,
    )
    scraper_name: Mapped[str | None] = mapped_column(Text)

    # HTTP provenance
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    http_method: Mapped[str | None] = mapped_column(String(4), default="GET")
    response_hash: Mapped[str | None] = mapped_column(String(64))

    # AI provenance
    ai_model: Mapped[str | None] = mapped_column(Text)
    ai_prompt_hash: Mapped[str | None] = mapped_column(String(64))
    ai_confidence: Mapped[int | None] = mapped_column(SmallInteger)

    # Timestamps
    observed_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    company = relationship(
        "Company", back_populates="evidence",
        primaryjoin="and_(EvidenceLedger.entity_type == 'company', "
                    "foreign(EvidenceLedger.entity_id) == Company.id)",
        viewonly=True,
        lazy="noload",
    )

    __table_args__ = (
        Index("idx_evidence_entity", entity_type, entity_id),
        Index("idx_evidence_field", entity_type, entity_id, field_name),
        Index("idx_evidence_source_domain", source_domain),
        Index("idx_evidence_scraper", scraper_name),
        Index("idx_evidence_observed", observed_at.desc()),
        Index("idx_evidence_method", source_method),
    )
