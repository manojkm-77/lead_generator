from datetime import datetime
from sqlalchemy import Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#3b82f6")  # hex color
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LeadTag(Base):
    __tablename__ = "lead_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), index=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), index=True)

    lead = relationship("Lead", back_populates="tags")
    tag = relationship("Tag")
