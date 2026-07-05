"""
BuyerHunter V2 — Core Engine & Data Layer

This package contains the refactored backend architecture:
  - models/        — SQLAlchemy ORM models (PostgreSQL-optimized)
  - schemas/       — Pydantic request/response models
  - engine/        — Intent Analyzer + Hybrid Query Planner
  - crawlers/      — Abstract adapter framework + source implementations
  - enrichment/    — Deep website link mapper
  - ddl.sql        — Production PostgreSQL DDL
"""

from backend.core.models import Company, Contact, EvidenceLedger, SearchJob
from backend.core.engine import IntentAnalyzer, HybridQueryPlanner
from backend.core.crawlers import BaseCrawlerAdapter, ALL_ADAPTERS
from backend.core.enrichment import LinkMapper, MappedSite

__all__ = [
    # Models
    "Company", "Contact", "EvidenceLedger", "SearchJob",
    # Engine
    "IntentAnalyzer", "HybridQueryPlanner",
    # Crawlers
    "BaseCrawlerAdapter", "ALL_ADAPTERS",
    # Enrichment
    "LinkMapper", "MappedSite",
]
