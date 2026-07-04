from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ProcurementContact(Base):
    """Contacts discovered from company websites with procurement-related titles."""
    __tablename__ = "procurement_contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), index=True)
    person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    designation: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    source_url: Mapped[str | None] = mapped_column(String(500))
    confidence_score: Mapped[int] = mapped_column(Integer, default=50)
    is_primary: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company = relationship("Company", backref="procurement_contacts")


class ProductDetection(Base):
    """Detected product consumption probabilities for a company."""
    __tablename__ = "product_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), unique=True, index=True)
    palm_oil: Mapped[float] = mapped_column(Float, default=0.0)
    rbd_palm_olein: Mapped[float] = mapped_column(Float, default=0.0)
    sunflower_oil: Mapped[float] = mapped_column(Float, default=0.0)
    soybean_oil: Mapped[float] = mapped_column(Float, default=0.0)
    rice_bran_oil: Mapped[float] = mapped_column(Float, default=0.0)
    mustard_oil: Mapped[float] = mapped_column(Float, default=0.0)
    groundnut_oil: Mapped[float] = mapped_column(Float, default=0.0)
    coconut_oil: Mapped[float] = mapped_column(Float, default=0.0)
    vanaspati: Mapped[float] = mapped_column(Float, default=0.0)
    shortening: Mapped[float] = mapped_column(Float, default=0.0)
    bakery_fat: Mapped[float] = mapped_column(Float, default=0.0)
    detection_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", backref="product_detection_rel")


class BuyerScore(Base):
    """Comprehensive buyer scoring for a company."""
    __tablename__ = "buyer_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), unique=True, index=True)

    # Sub-scores (each 0-12.5, total 0-100)
    palm_oil_relevance: Mapped[int] = mapped_column(Integer, default=0)
    consumption_score: Mapped[int] = mapped_column(Integer, default=0)
    size_score: Mapped[int] = mapped_column(Integer, default=0)
    import_score: Mapped[int] = mapped_column(Integer, default=0)
    procurement_score: Mapped[int] = mapped_column(Integer, default=0)
    completeness_score: Mapped[int] = mapped_column(Integer, default=0)
    activity_score: Mapped[int] = mapped_column(Integer, default=0)
    opportunity_score: Mapped[int] = mapped_column(Integer, default=0)

    # Consumption estimates
    monthly_consumption: Mapped[str | None] = mapped_column(String(100))
    annual_consumption: Mapped[str | None] = mapped_column(String(100))
    buying_frequency: Mapped[str | None] = mapped_column(String(50))

    # Company metrics
    company_size: Mapped[str | None] = mapped_column(String(50))
    manufacturing_capacity: Mapped[str | None] = mapped_column(String(100))

    # Buyer classification
    buyer_priority: Mapped[str | None] = mapped_column(String(20))  # A/B/C/D
    procurement_maturity: Mapped[str | None] = mapped_column(String(50))  # Basic/Developing/Advanced/Enterprise
    lead_temperature: Mapped[str | None] = mapped_column(String(20))  # Cold/Warm/Hot/Very Hot

    # Overall score
    buyer_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_breakdown: Mapped[str | None] = mapped_column(Text)  # JSON

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", backref="buyer_scores_rel")


class BuyerSummary(Base):
    """AI-generated buyer intelligence summary."""
    __tablename__ = "buyer_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), unique=True, index=True)

    company_summary: Mapped[str | None] = mapped_column(Text)
    why_buyer: Mapped[str | None] = mapped_column(Text)
    recommended_pitch: Mapped[str | None] = mapped_column(Text)
    suggested_products: Mapped[str | None] = mapped_column(Text)  # JSON array
    risk_level: Mapped[str | None] = mapped_column(String(20))
    best_first_contact: Mapped[str | None] = mapped_column(Text)
    followup_strategy: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company = relationship("Company", backref="buyer_summary_rel")
