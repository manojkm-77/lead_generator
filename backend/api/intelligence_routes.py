"""
BuyerHunter AI — Intelligence Engine + Lead Discovery Pipeline API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.services.intelligence import IntelligenceEngine
from backend.services.lead_pipeline import (
    LeadDiscoveryPipeline, get_pipeline_progress, get_all_pipelines, pipeline_event_stream,
)
from backend.services.search_planner import SearchPlanner
from backend.services.source_manager import get_source_registry
from backend.infrastructure.sse import get_sse_publisher
from backend.infrastructure.registry import get_worker

router = APIRouter()
engine = IntelligenceEngine()
pipeline = LeadDiscoveryPipeline()
planner = SearchPlanner()
source_registry = get_source_registry()


@router.get("/buyer-intelligence")
async def buyer_intelligence(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    min_score: int = Query(0, ge=0, le=100),
    industry: str | None = None,
    priority: str | None = None,
):
    """Get buyer intelligence for all analyzed companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from backend.models.intelligence import BuyerScore
    from sqlalchemy import select, func

    async with async_session() as db:
        query = (
            select(Company, BuyerScore)
            .join(BuyerScore, Company.id == BuyerScore.company_id)
            .where(BuyerScore.buyer_score >= min_score)
        )
        if industry:
            query = query.where(Company.industry == industry)
        if priority:
            query = query.where(BuyerScore.buyer_priority == priority)

        count_q = select(func.count(BuyerScore.id)).where(BuyerScore.buyer_score >= min_score)
        total = (await db.execute(count_q)).scalar() or 0

        query = query.order_by(BuyerScore.buyer_score.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        rows = result.all()

        items = []
        for company, score in rows:
            items.append({
                "company_id": company.id,
                "company_name": company.company_name,
                "industry": company.industry,
                "city": company.city,
                "website": company.website,
                "buyer_score": score.buyer_score,
                "buyer_priority": score.buyer_priority,
                "lead_temperature": score.lead_temperature,
                "annual_consumption": score.annual_consumption,
                "monthly_consumption": score.monthly_consumption,
                "buying_frequency": score.buying_frequency,
                "company_size": score.company_size,
                "procurement_maturity": score.procurement_maturity,
            })

        return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/procurement-contacts")
async def procurement_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    min_confidence: int = Query(0, ge=0, le=100),
    company_id: int | None = None,
):
    """Get all discovered procurement contacts."""
    from backend.database import async_session
    from backend.models.intelligence import ProcurementContact
    from backend.models.company import Company
    from sqlalchemy import select, func

    async with async_session() as db:
        query = select(ProcurementContact).where(
            ProcurementContact.confidence_score >= min_confidence
        )
        if company_id:
            query = query.where(ProcurementContact.company_id == company_id)

        count_q = select(func.count(ProcurementContact.id))
        total = (await db.execute(count_q)).scalar() or 0

        query = query.order_by(ProcurementContact.confidence_score.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        contacts = []
        for row in result.scalars().all():
            contacts.append({
                "id": row.id,
                "company_id": row.company_id,
                "person_name": row.person_name,
                "designation": row.designation,
                "email": row.email,
                "phone": row.phone,
                "linkedin_url": row.linkedin_url,
                "source_url": row.source_url,
                "confidence_score": row.confidence_score,
                "is_primary": row.is_primary,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        for contact in contacts:
            company = await db.get(Company, contact["company_id"])
            contact["company_name"] = company.company_name if company else "Unknown"

        return {"total": total, "page": page, "contacts": contacts}


@router.get("/top-buyers")
async def top_buyers(limit: int = Query(100, ge=1, le=500)):
    """Get top scoring buyers."""
    return await engine.get_top_buyers(limit)


@router.post("/analyze-company/{company_id}")
async def analyze_company(company_id: int, background_tasks: BackgroundTasks):
    """Run full intelligence analysis on a company."""
    background_tasks.add_task(engine.analyze_company, company_id)
    return {"status": "started", "company_id": company_id, "message": "Analysis queued"}


@router.post("/analyze-all")
async def analyze_all(
    limit: int = Query(50, ge=1, le=200),
    min_score: int = Query(0, ge=0, le=100),
    background_tasks: BackgroundTasks = None,
):
    """Analyze all unprocessed companies."""
    background_tasks.add_task(engine.analyze_batch, limit, min_score)
    return {"status": "started", "limit": limit, "message": f"Batch analysis queued (up to {limit})"}


@router.get("/intelligence/stats")
async def intelligence_stats():
    """Get intelligence engine statistics."""
    from backend.database import async_session
    from backend.models.intelligence import BuyerScore, ProcurementContact, ProductDetection
    from backend.models.company import Company
    from sqlalchemy import select, func

    async with async_session() as db:
        total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
        analyzed = (await db.execute(select(func.count(BuyerScore.id)))).scalar() or 0
        contacts = (await db.execute(select(func.count(ProcurementContact.id)))).scalar() or 0
        products = (await db.execute(select(func.count(ProductDetection.id)))).scalar() or 0

        # Score distribution
        score_dist = {}
        for label, low, high in [("0-25", 0, 25), ("26-50", 26, 50), ("51-75", 51, 75), ("76-100", 76, 100)]:
            count = (await db.execute(
                select(func.count(BuyerScore.id)).where(
                    BuyerScore.buyer_score >= low, BuyerScore.buyer_score <= high
                )
            )).scalar() or 0
            score_dist[label] = count

        # Priority distribution
        priority_result = await db.execute(
            select(BuyerScore.buyer_priority, func.count(BuyerScore.id))
            .group_by(BuyerScore.buyer_priority)
        )
        priority_dist = {r[0]: r[1] for r in priority_result.all()}

        return {
            "total_companies": total_companies,
            "analyzed": analyzed,
            "contacts_found": contacts,
            "products_detected": products,
            "score_distribution": score_dist,
            "priority_distribution": priority_dist,
            "analysis_rate": round(analyzed / total_companies * 100, 1) if total_companies > 0 else 0,
        }


@router.get("/intelligence/{company_id}")
async def get_intelligence(company_id: int):
    """Get full intelligence data for a company."""
    data = await engine.get_intelligence(company_id)
    if not data:
        raise HTTPException(status_code=404, detail="Company not found")
    return data


# ── Lead Discovery Pipeline ──────────────────────────────────────────────────


class PipelineRequest(BaseModel):
    query: str
    max_queries: int = 200
    max_pages_per_spider: int = 3
    sources: list[str] | None = None
    max_concurrent: int = 4
    skip_enrich: bool = False
    skip_score: bool = False
    skip_verify: bool = False


@router.post("/pipeline/start")
async def start_pipeline(request: PipelineRequest):
    """Start a lead discovery pipeline. Returns run_id for SSE tracking."""
    run_id = await pipeline.run(
        query=request.query,
        max_queries=request.max_queries,
        max_pages_per_spider=request.max_pages_per_spider,
        sources=request.sources,
        max_concurrent=request.max_concurrent,
        skip_enrich=request.skip_enrich,
        skip_score=request.skip_score,
        skip_verify=request.skip_verify,
    )
    return {
        "status": "started",
        "run_id": run_id,
        "message": f"Pipeline started for '{request.query}'",
    }


@router.get("/pipeline/{run_id}/progress")
async def pipeline_progress(run_id: str):
    """Get current pipeline progress."""
    progress = get_pipeline_progress(run_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return progress


@router.get("/pipeline/{run_id}/stream")
async def pipeline_stream(run_id: str):
    """SSE endpoint for live pipeline progress updates."""
    progress = get_pipeline_progress(run_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return StreamingResponse(
        pipeline_event_stream(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/pipeline/active")
async def active_pipelines():
    """Get all active pipeline runs."""
    return {"pipelines": get_all_pipelines()}


@router.get("/pipeline/expand")
async def expand_query(query: str = Query(..., min_length=1), max_queries: int = Query(500, ge=1, le=1000)):
    """Preview search query expansion without running crawls."""
    return await planner.preview_expansion(query, max_queries=max_queries)


# ── Discovery Engine Endpoints ────────────────────────────────────────────────


# ── Infrastructure & Worker Metrics SSE ──────────────────────────────────


@router.get("/infrastructure/stream")
async def worker_metrics_stream(request: Request):
    """SSE endpoint for real-time worker metrics."""
    sse = get_sse_publisher()
    queue = await sse.subscribe()
    return StreamingResponse(
        sse.event_generator(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/infrastructure/metrics")
async def worker_metrics():
    """Get current worker metrics snapshot."""
    sse = get_sse_publisher()
    metrics = await sse.get_metrics()
    worker = get_worker()
    if worker:
        stats = await worker.stats()
        return {**metrics, "infrastructure": stats}
    return metrics


@router.get("/infrastructure/health")
async def infrastructure_health():
    """Get infrastructure health status."""
    from backend.infrastructure.redis import is_redis_available
    worker = get_worker()
    return {
        "redis_connected": is_redis_available(),
        "worker_running": worker is not None and worker._running if worker else False,
        "worker_concurrency": worker._concurrency if worker else 0,
    }


@router.post("/infrastructure/queues/flush")
async def flush_queues():
    """Flush all queues and reset state."""
    from backend.infrastructure.queue import SearchJobQueue, URLDiscoveryQueue
    await SearchJobQueue().flush()
    await URLDiscoveryQueue().flush()
    from backend.infrastructure.rate_limiter import DomainRateLimiter
    from backend.infrastructure.proxy import ProxyRotator
    from backend.infrastructure.retry import RetryManager
    await DomainRateLimiter().flush()
    await ProxyRotator().flush()
    await RetryManager().flush()
    sse = get_sse_publisher()
    await sse.reset_metrics()
    return {"status": "all queues flushed"}


@router.post("/infrastructure/worker/restart")
async def restart_worker():
    """Restart the discovery worker pool."""
    worker = get_worker()
    if worker:
        await worker.stop()
        from backend.config import get_settings
        settings = get_settings()
        worker._concurrency = settings.worker_concurrency
        await worker.start()
        return {"status": "worker restarted"}
    return {"status": "no worker running"}


# ── Discovery Endpoints ─────────────────────────────────────────────────


@router.get("/discovery/sources")
async def discovery_sources():
    """Get all available discovery sources."""
    return {
        "sources": source_registry.get_summary(),
        "total": len(source_registry.get_all()),
    }


@router.post("/discovery/plan")
async def discovery_plan(query: str = Query(..., min_length=1), max_queries: int = Query(500, ge=1, le=1000)):
    """Preview the discovery plan without executing crawls."""
    plan = await planner.preview_expansion(query, max_queries=max_queries)
    return plan


@router.get("/discovery/companies/{run_id}")
async def discovery_companies(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get companies discovered in a pipeline run."""
    import sqlite3
    conn = sqlite3.connect("buyerhunter.db")
    conn.row_factory = sqlite3.Row

    # Get pipeline run info to find when it started
    pipeline_start = conn.execute(
        "SELECT MIN(created_at) as start_time FROM crawl_jobs WHERE run_id = ?",
        (run_id,),
    ).fetchone()

    if not pipeline_start or not pipeline_start["start_time"]:
        conn.close()
        return {"total": 0, "page": page, "companies": []}

    start_time = pipeline_start["start_time"]
    offset = (page - 1) * page_size

    total = conn.execute(
        """SELECT COUNT(*) FROM companies WHERE created_at >= ?
        OR updated_at >= ?""",
        (start_time, start_time),
    ).fetchone()[0]

    rows = conn.execute(
        """SELECT * FROM companies WHERE created_at >= ?
        OR updated_at >= ?
        ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        (start_time, start_time, page_size, offset),
    ).fetchall()

    companies = [dict(r) for r in rows]
    conn.close()

    return {"total": total, "page": page, "companies": companies}


@router.get("/discovery/stats")
async def discovery_stats():
    """Get overall discovery engine statistics."""
    import sqlite3
    conn = sqlite3.connect("buyerhunter.db")

    total_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    total_verified = conn.execute("SELECT COUNT(*) FROM companies WHERE is_verified = 1").fetchone()[0]
    total_with_email = conn.execute("SELECT COUNT(*) FROM companies WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    total_with_phone = conn.execute("SELECT COUNT(*) FROM companies WHERE phone IS NOT NULL AND phone != ''").fetchone()[0]
    total_with_website = conn.execute("SELECT COUNT(*) FROM companies WHERE website IS NOT NULL AND website != ''").fetchone()[0]
    total_scored = conn.execute("SELECT COUNT(*) FROM companies WHERE lead_score > 0").fetchone()[0]
    total_enriched = conn.execute("SELECT COUNT(*) FROM companies WHERE enriched_at IS NOT NULL").fetchone()[0]

    # Pipeline runs
    active_runs = conn.execute(
        "SELECT COUNT(*) FROM crawl_jobs WHERE status IN ('queued', 'running')"
    ).fetchone()[0]

    total_jobs = conn.execute("SELECT COUNT(*) FROM crawl_jobs").fetchone()[0]

    # Source breakdown
    by_source = conn.execute(
        "SELECT source, COUNT(*) as count FROM companies WHERE source IS NOT NULL GROUP BY source ORDER BY count DESC"
    ).fetchall()
    sources = [{"source": r[0], "count": r[1]} for r in by_source]

    conn.close()

    return {
        "total_companies": total_companies,
        "verified": total_verified,
        "with_email": total_with_email,
        "with_phone": total_with_phone,
        "with_website": total_with_website,
        "scored": total_scored,
        "enriched": total_enriched,
        "active_runs": active_runs,
        "total_jobs": total_jobs,
        "by_source": sources,
    }


# ── Analytics ────────────────────────────────────────────────────────────────


@router.get("/analytics/states")
async def analytics_by_state():
    """Get company count by state."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select, func

    async with async_session() as db:
        result = await db.execute(
            select(Company.state, func.count(Company.id))
            .where(Company.state.isnot(None), Company.state != "")
            .group_by(Company.state)
            .order_by(func.count(Company.id).desc())
        )
        return [{"state": r[0], "count": r[1]} for r in result.all()]


@router.get("/analytics/industries")
async def analytics_by_industry():
    """Get company count by industry."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select, func

    async with async_session() as db:
        result = await db.execute(
            select(Company.industry, func.count(Company.id))
            .where(Company.industry.isnot(None), Company.industry != "Unknown")
            .group_by(Company.industry)
            .order_by(func.count(Company.id).desc())
        )
        return [{"industry": r[0], "count": r[1]} for r in result.all()]


@router.get("/analytics/sources")
async def analytics_by_source():
    """Get company count by data source."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select, func

    async with async_session() as db:
        result = await db.execute(
            select(Company.source, func.count(Company.id))
            .where(Company.source.isnot(None))
            .group_by(Company.source)
            .order_by(func.count(Company.id).desc())
        )
        return [{"source": r[0], "count": r[1]} for r in result.all()]


@router.get("/analytics/top-buyers")
async def analytics_top_buyers(limit: int = Query(20, ge=1, le=100)):
    """Get top scoring buyer companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Company)
            .where(Company.lead_score > 0)
            .order_by(Company.lead_score.desc())
            .limit(limit)
        )
        companies = []
        for c in result.scalars().all():
            companies.append({
                "id": c.id,
                "company_name": c.company_name,
                "industry": c.industry,
                "city": c.city,
                "state": c.state,
                "lead_score": c.lead_score,
                "email": c.email,
                "phone": c.phone,
                "website": c.website,
                "is_manufacturer": c.is_manufacturer,
                "is_importer": c.is_importer,
            })
        return {"total": len(companies), "companies": companies}


@router.get("/analytics/top-manufacturers")
async def analytics_top_manufacturers(limit: int = Query(20, ge=1, le=100)):
    """Get top manufacturer companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Company)
            .where(Company.is_manufacturer == True)
            .order_by(Company.lead_score.desc())
            .limit(limit)
        )
        return [{"id": c.id, "company_name": c.company_name, "industry": c.industry,
                 "city": c.city, "state": c.state, "lead_score": c.lead_score}
                for c in result.scalars().all()]


@router.get("/analytics/top-distributors")
async def analytics_top_distributors(limit: int = Query(20, ge=1, le=100)):
    """Get top distributor companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Company)
            .where(Company.is_distributor == True)
            .order_by(Company.lead_score.desc())
            .limit(limit)
        )
        return [{"id": c.id, "company_name": c.company_name, "industry": c.industry,
                 "city": c.city, "state": c.state, "lead_score": c.lead_score}
                for c in result.scalars().all()]


@router.get("/analytics/top-importers")
async def analytics_top_importers(limit: int = Query(20, ge=1, le=100)):
    """Get top importer companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Company)
            .where(Company.is_importer == True)
            .order_by(Company.lead_score.desc())
            .limit(limit)
        )
        return [{"id": c.id, "company_name": c.company_name, "industry": c.industry,
                 "city": c.city, "state": c.state, "lead_score": c.lead_score}
                for c in result.scalars().all()]


@router.get("/analytics/top-exporters")
async def analytics_top_exporters(limit: int = Query(20, ge=1, le=100)):
    """Get top exporter companies."""
    from backend.database import async_session
    from backend.models.company import Company
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(
            select(Company)
            .where(Company.is_exporter == True)
            .order_by(Company.lead_score.desc())
            .limit(limit)
        )
        return [{"id": c.id, "company_name": c.company_name, "industry": c.industry,
                 "city": c.city, "state": c.state, "lead_score": c.lead_score}
                for c in result.scalars().all()]


# ── Verification & Deduplication ──────────────────────────────────────────────


@router.post("/verify/batch")
async def verify_batch(
    limit: int = Query(100, ge=1, le=500),
    background_tasks: BackgroundTasks = None,
):
    """Batch verify companies across sources."""
    from backend.services.verification import VerificationEngine
    verifier = VerificationEngine()
    background_tasks.add_task(verifier.batch_verify, limit, 0)
    return {"status": "started", "limit": limit, "message": f"Batch verification queued for up to {limit} companies"}


@router.get("/dedup/stats")
async def dedup_stats():
    """Get deduplication statistics."""
    from backend.services.deduplication import DeduplicationEngine
    dedup = DeduplicationEngine()
    return dedup.get_merge_stats()


@router.get("/pipeline/{run_id}/jobs")
async def pipeline_jobs(run_id: str):
    """Get all crawl jobs for a pipeline run."""
    from backend.services.crawl_queue import CrawlJobQueue
    queue = CrawlJobQueue()
    jobs = queue.get_run_jobs(run_id)
    stats = queue.get_run_stats(run_id)
    return {"run_id": run_id, "stats": stats, "jobs": jobs}


@router.get("/pipeline/{run_id}/cancel")
async def cancel_pipeline(run_id: str):
    """Cancel a running pipeline."""
    from backend.services.crawl_queue import CrawlJobQueue
    from backend.services.search_planner import _progress_store
    queue = CrawlJobQueue()
    queue.cancel_run(run_id)
    progress = _progress_store.get(run_id)
    if progress:
        progress.status = "cancelled"
        progress.add_message("Pipeline cancelled by user")
    return {"status": "cancelled", "run_id": run_id}
