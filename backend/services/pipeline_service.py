"""
BuyerHunter Pipeline Service

Full crawl → save → evidence → dedup → merge pipeline.
Handles provenance tracking, field-level confidence, and deduplication.
"""

import logging
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.models.company import Company
from backend.core.models.contact import Contact, ContactChannel, ContactPurpose
from backend.core.models.evidence_ledger import EvidenceCategory, EvidenceLedger

logger = logging.getLogger(__name__)


def _field_confidence(field_name: str, value: Any, source: str) -> int:
    """Score confidence for an individual field based on source and content."""
    if not value:
        return 0
    base = 50
    source_bonus = {
        "apeda": 20, "gst_directory": 20, "company_website": 15,
        "indiamart": 10, "tradeindia": 10, "exportersindia": 10,
        "justdial": 5, "yellowpages": 5, "googlemaps": 3,
    }
    base += source_bonus.get(source, 0)
    s = str(value)
    if field_name in ("website_url", "canonical_name") and len(s) > 3:
        base += 20
    if field_name == "email" and re.match(r"[^@]+@[^@]+\.[^@]+", s):
        base += 15
    if field_name == "phone" and re.sub(r"[^\d]", "", s).startswith(("6", "7", "8", "9")):
        base += 10
    if field_name == "gst_number" and len(s) == 15:
        base += 25
    if field_name == "person_name" and len(s.split()) >= 2:
        base += 10
    return min(99, base)


async def save_company_with_evidence(
    db: AsyncSession,
    company_data: dict,
    source: str,
    source_url: str,
    scraper_name: str,
    evidence_category: EvidenceCategory = EvidenceCategory.SCRAPED_DIRECT,
) -> Company | None:
    """Save a company and record evidence ledger entries for every field."""
    name = company_data.get("company_name", "")
    if not name or len(name) < 2:
        return None

    result = await db.execute(
        select(Company).where(Company.canonical_name == name)
    )
    if result.scalars().first():
        return None

    # Use None for empty strings to avoid unique constraint violations
    gst_val = company_data.get("gst_number", "") or None
    iec_val = company_data.get("iec_code", "") or None
    fssai_val = company_data.get("fssai_number", "") or None
    cin_val = company_data.get("cin_number", "") or None
    pan_val = company_data.get("pan_number", "") or None

    company = Company(
        canonical_name=name,
        legal_name=company_data.get("legal_name", "") or None,
        website_url=company_data.get("website", "") or None,
        hq_country=company_data.get("country", "IN"),
        hq_state=company_data.get("state", "") or None,
        hq_city=company_data.get("city", "") or None,
        hq_address=company_data.get("address", "") or None,
        latitude=company_data.get("latitude"),
        longitude=company_data.get("longitude"),
        gst_number=gst_val,
        iec_code=iec_val,
        fssai_number=fssai_val,
        cin_number=cin_val,
        pan_number=pan_val,
        industry=company_data.get("industry", "") or None,
        sub_industry=company_data.get("sub_industry", "") or None,
        buyer_score=company_data.get("buyer_score", 50),
        confidence=company_data.get("confidence", 50),
        first_seen_source=source,
        first_seen_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(company)
    await db.flush()

    parsed = urlparse(source_url) if source_url else None
    domain = parsed.netloc if parsed else ""

    field_map = {
        "canonical_name": company.canonical_name,
        "website_url": company.website_url,
        "gst_number": company.gst_number,
        "iec_code": company.iec_code,
        "fssai_number": company.fssai_number,
        "industry": company.industry,
        "hq_city": company.hq_city,
        "hq_state": company.hq_state,
        "hq_address": company.hq_address,
        "hq_country": company.hq_country,
        "buyer_score": str(company.buyer_score),
        "confidence": str(company.confidence),
    }
    now = datetime.now(timezone.utc)
    for fname, fvalue in field_map.items():
        if not fvalue:
            continue
        cf = _field_confidence(fname, fvalue, source)
        db.add(EvidenceLedger(
            entity_type="company",
            entity_id=company.id,
            field_name=fname,
            field_value=str(fvalue),
            source_url=source_url,
            source_domain=domain,
            source_method=evidence_category,
            scraper_name=scraper_name,
            http_status=200,
            http_method="GET",
            observed_at=now,
            created_at=now,
        ))

    return company


async def save_contact_with_evidence(
    db: AsyncSession,
    company_id: int,
    channel: ContactChannel,
    channel_value: str,
    source_url: str,
    scraper_name: str,
    person_name: str = "",
    designation: str = "",
    purpose: ContactPurpose = ContactPurpose.GENERAL,
    confidence: int = 50,
    evidence_category: EvidenceCategory = EvidenceCategory.SCRAPED_DIRECT,
) -> Contact | None:
    """Save a contact with provenance. Skips duplicates."""
    if not channel_value:
        return None

    result = await db.execute(
        select(Contact).where(
            Contact.company_id == company_id,
            Contact.channel == channel,
            Contact.channel_value == channel_value,
        )
    )
    if result.scalars().first():
        return None

    now = datetime.now(timezone.utc)
    contact = Contact(
        company_id=company_id,
        person_name=person_name or None,
        designation=designation or None,
        channel=channel,
        channel_value=channel_value,
        channel_purpose=purpose,
        confidence=confidence,
        is_verified=False,
        created_at=now,
        updated_at=now,
    )
    db.add(contact)
    await db.flush()

    parsed = urlparse(source_url) if source_url else None
    domain = parsed.netloc if parsed else ""

    for fname, fvalue in [
        ("person_name", contact.person_name),
        ("designation", contact.designation),
        ("channel_value", contact.channel_value),
    ]:
        if not fvalue:
            continue
        cf = _field_confidence(fname, fvalue, scraper_name)
        db.add(EvidenceLedger(
            entity_type="contact",
            entity_id=contact.id,
            field_name=fname,
            field_value=str(fvalue),
            source_url=source_url,
            source_domain=domain,
            source_method=evidence_category,
            scraper_name=scraper_name,
            http_status=200,
            http_method="GET",
            observed_at=now,
            created_at=now,
        ))

    return contact


# ─── V2 Dedup & Merge ─────────────────────────────────────────────────────

MATCH_PRIORITY_FIELDS = [
    ("website_url", lambda c: str((c.website_url or "")).lower().rstrip("/")),
    ("gst_number", lambda c: str(c.gst_number or "")),
    ("iec_code", lambda c: str(c.iec_code or "")),
]


async def find_duplicate(db: AsyncSession, company: Company) -> Company | None:
    """Find a duplicate using matching priority: website > GST > IEC > name."""
    for field_name, getter in MATCH_PRIORITY_FIELDS:
        val = getter(company)
        if not val or len(val) < 3:
            continue
        result = await db.execute(
            select(Company).where(
                getattr(Company, field_name) == val,
                Company.id != company.id,
            )
        )
        match = result.scalars().first()
        if match:
            return match

    # Fuzzy name match
    name = (company.canonical_name or "").strip().lower()
    if len(name) >= 5:
        words = name.split()
        if words:
            result = await db.execute(
                select(Company).where(
                    Company.canonical_name.ilike(f"%{words[0]}%"),
                    Company.id != company.id,
                ).limit(20)
            )
            for row in result.scalars().all():
                existing = (row.canonical_name or "").lower()
                ratio = SequenceMatcher(None, name, existing).ratio()
                if ratio >= 0.75:
                    return row
    return None


async def merge_company_into(
    db: AsyncSession,
    survivor: Company,
    duplicate: Company,
    source: str,
) -> dict:
    """Merge duplicate into survivor. Fills empty fields, never overwrites."""
    now = datetime.now(timezone.utc)
    merged_fields = []

    text_fields = [
        "website_url", "gst_number", "iec_code", "fssai_number",
        "industry", "sub_industry", "hq_city", "hq_state",
        "hq_country", "hq_address",
    ]
    for field in text_fields:
        existing = getattr(survivor, field) or ""
        new_val = getattr(duplicate, field) or ""
        if not existing and new_val:
            setattr(survivor, field, new_val)
            merged_fields.append(field)
            db.add(EvidenceLedger(
                entity_type="company",
                entity_id=survivor.id,
                field_name=field,
                field_value=str(new_val),
                source_url="",
                source_domain="",
                source_method=EvidenceCategory.SCRAPED_DIRECT,
                scraper_name=f"merge_from_{source}",
                http_status=200,
                observed_at=now,
                created_at=now,
            ))

    if duplicate.buyer_score and duplicate.buyer_score > (survivor.buyer_score or 0):
        survivor.buyer_score = duplicate.buyer_score
        merged_fields.append("buyer_score")

    if duplicate.confidence and duplicate.confidence > (survivor.confidence or 0):
        survivor.confidence = duplicate.confidence
        merged_fields.append("confidence")

    source_attr = duplicate.first_seen_source or ""
    if source_attr and source_attr not in (survivor.first_seen_source or ""):
        survivor.first_seen_source = f"{survivor.first_seen_source},{source_attr}" if survivor.first_seen_source else source_attr
        merged_fields.append("first_seen_source")

    survivor.updated_at = now

    # Merge contacts from duplicate into survivor
    ct_result = await db.execute(
        select(Contact).where(Contact.company_id == duplicate.id)
    )
    for ct in ct_result.scalars().all():
        exists = await db.execute(
            select(Contact).where(
                Contact.company_id == survivor.id,
                Contact.channel == ct.channel,
                Contact.channel_value == ct.channel_value,
            )
        )
        if not exists.scalars().first():
            ct.company_id = survivor.id
            db.add(ct)
            merged_fields.append(f"contact:{ct.channel}")

    # Delete the duplicate company
    await db.delete(duplicate)

    return {"merged_fields": merged_fields, "survivor_id": survivor.id, "merged_id": duplicate.id}


async def run_dedup_pipeline(db: AsyncSession) -> dict:
    """Run deduplication on all companies in the V2 DB."""
    result = await db.execute(select(Company).order_by(Company.created_at))
    companies = result.scalars().all()

    new_count = len(companies)
    merged_count = 0
    removed_count = 0
    kept_ids = set()

    for company in companies:
        if company.id in kept_ids:
            continue
        dup = await find_duplicate(db, company)
        if dup:
            if dup.id in kept_ids:
                continue
            merge_result = await merge_company_into(db, company, dup, "dedup")
            kept_ids.add(company.id)
            merged_count += 1
            removed_count += 1
        else:
            kept_ids.add(company.id)

    await db.commit()

    return {
        "total_before_dedup": new_count,
        "after_dedup": len(kept_ids),
        "merged": merged_count,
        "removed": removed_count,
    }


# ─── Crawl Dashboard ──────────────────────────────────────────────────────

async def get_crawl_dashboard(db: AsyncSession) -> dict:
    """Aggregate crawl dashboard stats from the DB."""
    total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
    total_contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0
    emails = (await db.execute(
        select(func.count(Contact.id)).where(Contact.channel == "email")
    )).scalar() or 0
    phones = (await db.execute(
        select(func.count(Contact.id)).where(Contact.channel == "phone")
    )).scalar() or 0
    whatsapps = (await db.execute(
        select(func.count(Contact.id)).where(Contact.channel == "whatsapp")
    )).scalar() or 0
    contacts_with_names = (await db.execute(
        select(func.count(Contact.id)).where(
            Contact.person_name.isnot(None),
            Contact.person_name != "",
        )
    )).scalar() or 0
    evidence_entries = (await db.execute(
        select(func.count(EvidenceLedger.id))
    )).scalar() or 0

    source_breakdown = await db.execute(
        select(Company.first_seen_source, func.count(Company.id))
        .group_by(Company.first_seen_source)
    )
    sources = {row[0] or "unknown": row[1] for row in source_breakdown.all()}

    avg_confidence = (await db.execute(
        select(func.avg(Company.confidence))
    )).scalar() or 0

    has_website = (await db.execute(
        select(func.count(Company.id)).where(
            Company.website_url.isnot(None), Company.website_url != ""
        )
    )).scalar() or 0

    return {
        "total_companies": total_companies,
        "total_contacts": total_contacts,
        "emails": emails,
        "phones": phones,
        "whatsapps": whatsapps,
        "contacts_with_names": contacts_with_names,
        "evidence_entries": evidence_entries,
        "sources": sources,
        "source_count": len(sources),
        "avg_confidence": round(float(avg_confidence), 1),
        "has_website": has_website,
    }
