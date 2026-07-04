import logging
from datetime import datetime, timedelta
from sqlalchemy import func, select, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.company import Company
from backend.models.crawl_log import CrawlLog
from backend.models.contact import Contact
from backend.models.lead import Lead

logger = logging.getLogger(__name__)


async def get_dashboard_stats(db: AsyncSession) -> dict:
    total = (await db.execute(select(func.count(Company.id)))).scalar() or 0

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = (await db.execute(
        select(func.count(Company.id)).where(Company.created_at >= today_start)
    )).scalar() or 0

    high_quality = (await db.execute(
        select(func.count(Company.id)).where(
            Company.lead_score >= 70
        )
    )).scalar() or 0

    emails_found = (await db.execute(
        select(func.count(Company.id)).where(Company.email.isnot(None), Company.email != "")
    )).scalar() or 0

    phones_found = (await db.execute(
        select(func.count(Company.id)).where(Company.phone.isnot(None), Company.phone != "")
    )).scalar() or 0

    websites_found = (await db.execute(
        select(func.count(Company.id)).where(Company.website.isnot(None), Company.website != "")
    )).scalar() or 0

    cities = (await db.execute(
        select(func.count(func.distinct(Company.city))).where(Company.city.isnot(None))
    )).scalar() or 0

    states = (await db.execute(
        select(func.count(func.distinct(Company.state))).where(Company.state.isnot(None))
    )).scalar() or 0

    countries = (await db.execute(
        select(func.count(func.distinct(Company.country))).where(Company.country.isnot(None))
    )).scalar() or 0

    # New field counts
    importers = (await db.execute(
        select(func.count(Company.id)).where(Company.is_importer == True)
    )).scalar() or 0

    exporters = (await db.execute(
        select(func.count(Company.id)).where(Company.is_exporter == True)
    )).scalar() or 0

    manufacturers = (await db.execute(
        select(func.count(Company.id)).where(Company.is_manufacturer == True)
    )).scalar() or 0

    distributors = (await db.execute(
        select(func.count(Company.id)).where(Company.is_distributor == True)
    )).scalar() or 0

    wholesalers = (await db.execute(
        select(func.count(Company.id)).where(Company.is_wholesaler == True)
    )).scalar() or 0

    high_intent = (await db.execute(
        select(func.count(Company.id)).where(
            Company.lead_score >= 80
        )
    )).scalar() or 0

    verified = (await db.execute(
        select(func.count(Company.id)).where(Company.lead_score >= 70)
    )).scalar() or 0

    # Active crawlers
    active_crawlers = (await db.execute(
        select(func.count(CrawlLog.id)).where(CrawlLog.status == "running")
    )).scalar() or 0

    # Score distribution
    score_distribution = {}
    for label, low, high in [
        ("0-20", 0, 20), ("21-40", 21, 40), ("41-60", 41, 60),
        ("61-80", 61, 80), ("81-100", 81, 100),
    ]:
        count = (await db.execute(
            select(func.count(Company.id)).where(
                Company.lead_score >= low, Company.lead_score <= high
            )
        )).scalar() or 0
        score_distribution[label] = count

    # Source breakdown
    source_result = await db.execute(
        select(Company.source, func.count(Company.id))
        .where(Company.source.isnot(None))
        .group_by(Company.source)
    )
    source_breakdown = {row[0]: row[1] for row in source_result.all()}

    # Industry breakdown
    industry_result = await db.execute(
        select(Company.industry, func.count(Company.id))
        .where(Company.industry.isnot(None), Company.industry != "Unknown")
        .group_by(Company.industry)
        .order_by(func.count(Company.id).desc())
        .limit(10)
    )
    industry_breakdown = {row[0]: row[1] for row in industry_result.all()}

    # State breakdown
    state_result = await db.execute(
        select(Company.state, func.count(Company.id))
        .where(Company.state.isnot(None), Company.state != "")
        .group_by(Company.state)
        .order_by(func.count(Company.id).desc())
        .limit(10)
    )
    state_breakdown = {row[0]: row[1] for row in state_result.all()}

    # Country breakdown
    country_result = await db.execute(
        select(Company.country, func.count(Company.id))
        .where(Company.country.isnot(None))
        .group_by(Company.country)
        .order_by(func.count(Company.id).desc())
        .limit(10)
    )
    country_breakdown = {row[0]: row[1] for row in country_result.all()}

    # Recent activity (last 14 days)
    recent_counts = []
    for i in range(13, -1, -1):
        day = today_start - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = (await db.execute(
            select(func.count(Company.id)).where(
                Company.created_at >= day, Company.created_at < next_day
            )
        )).scalar() or 0
        recent_counts.append({"date": day.strftime("%Y-%m-%d"), "count": count})

    # Recent crawls
    recent_crawls_result = await db.execute(
        select(CrawlLog).order_by(CrawlLog.start_time.desc()).limit(5)
    )
    recent_crawls = []
    for row in recent_crawls_result.scalars().all():
        recent_crawls.append({
            "id": row.id,
            "spider_name": row.spider_name,
            "status": row.status,
            "start_time": row.start_time.isoformat() if row.start_time else None,
        })

    return {
        "total_companies": total,
        "today_new_leads": today_new,
        "high_quality_leads": high_quality,
        "verified_buyers": verified,
        "emails_found": emails_found,
        "phones_found": phones_found,
        "websites_found": websites_found,
        "importers": importers,
        "exporters": exporters,
        "manufacturers": manufacturers,
        "distributors": distributors,
        "wholesalers": wholesalers,
        "high_intent_buyers": high_intent,
        "active_crawlers": active_crawlers,
        "cities": cities,
        "states": states,
        "countries": countries,
        "score_distribution": score_distribution,
        "source_breakdown": source_breakdown,
        "industry_breakdown": industry_breakdown,
        "state_breakdown": state_breakdown,
        "country_breakdown": country_breakdown,
        "recent_activity": recent_counts,
        "recent_crawls": recent_crawls,
    }


async def get_crawl_logs(db: AsyncSession, limit: int = 20) -> list[dict]:
    result = await db.execute(
        select(CrawlLog).order_by(CrawlLog.start_time.desc()).limit(limit)
    )
    return [dict(row._mapping) for row in result.all()]
