"""
BuyerHunter V2 — Search Job Model

Tracks the full lifecycle of search queries: from planning through
execution to completion. Supports retry, priority queuing, parent-child
relationships for expanded queries, and geography targeting.
"""

import enum
import json
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Enum, ForeignKey, Index, Integer, SmallInteger, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from backend.core.database import V2Base


class _JsonText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    RATE_LIMITED = "rate_limited"


class JobPriority(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# Priority ordering for ORDER BY
PRIORITY_ORDER = {
    JobPriority.CRITICAL: 0,
    JobPriority.HIGH: 1,
    JobPriority.NORMAL: 2,
    JobPriority.LOW: 3,
}


class SearchJob(V2Base):
    __tablename__ = "search_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Query
    query_string: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str | None] = mapped_column(String(64))

    # Source
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)

    # Lifecycle
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False), default=JobStatus.PENDING
    )
    priority: Mapped[JobPriority] = mapped_column(
        Enum(JobPriority, native_enum=False), default=JobPriority.NORMAL
    )
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    max_retries: Mapped[int] = mapped_column(SmallInteger, default=3)
    max_pages: Mapped[int] = mapped_column(SmallInteger, default=5)

    # Result tracking
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0)
    companies_found: Mapped[int] = mapped_column(Integer, default=0)
    contacts_found: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[dict | None] = mapped_column(
        JSONB().with_variant(_JsonText(), "sqlite")
    )

    # Geography
    target_state: Mapped[str | None] = mapped_column(Text)
    target_city: Mapped[str | None] = mapped_column(Text)
    target_country: Mapped[str | None] = mapped_column(String(5), default="IN")

    # Parent relationship
    parent_job_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("search_jobs.id", ondelete="SET NULL")
    )
    run_id: Mapped[str | None] = mapped_column(String(64))

    # Scheduling
    scheduled_at: Mapped[datetime | None] = mapped_column()
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    parent_job = relationship(
        "SearchJob", remote_side=[id], lazy="noload",
    )

    __table_args__ = (
        Index("idx_jobs_status_priority", status, priority),
        Index("idx_jobs_source", source),
        Index("idx_jobs_run", run_id),
        Index("idx_jobs_parent", parent_job_id),
        Index("idx_jobs_query_hash", query_hash),
        Index("idx_jobs_created", created_at.desc()),
        Index("idx_jobs_retry", retry_count, status,
              postgresql_where="status = 'failed'"),
    )
