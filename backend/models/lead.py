from datetime import datetime
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Lead(Base):
    """CRM lead - linked to a Company, tracks sales pipeline."""
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(Integer, ForeignKey("companies.id"), index=True)
    salesperson_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("salesperson.id"), index=True)

    # Pipeline status
    status: Mapped[str] = mapped_column(String(20), default="cold", index=True)
    # cold, warm, hot, interested, negotiation, won, lost

    # Sales tracking
    deal_value: Mapped[int | None] = mapped_column(Integer)  # in INR
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low, medium, high, urgent
    lost_reason: Mapped[str | None] = mapped_column(Text)

    # Follow-up
    next_followup: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    last_contacted: Mapped[datetime | None] = mapped_column(DateTime)
    followup_notes: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    company = relationship("Company", backref="leads")
    salesperson = relationship("Salesperson", backref="leads")
    notes = relationship("Note", back_populates="lead", cascade="all, delete-orphan")
    activities = relationship("Activity", back_populates="lead", cascade="all, delete-orphan")
    tags = relationship("LeadTag", back_populates="lead", cascade="all, delete-orphan")
    attachments = relationship("Attachment", back_populates="lead", cascade="all, delete-orphan")
