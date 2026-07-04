"""
BuyerHunter AI — Intelligence Engine + Lead Discovery Pipeline API Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.services.intelligence import IntelligenceEngine
from backend.services.lead_pipeline import (
    LeadDiscoveryPipeline, get_pipeline_progress, get_all_pipelines, pipeline_event_stream,
)
from backend.services.query_expander import QueryExpander

router = APIRouter()
engine = IntelligenceEngine()
pipeline = LeadDiscoveryPipeline()
expander = QueryExpander()


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
    max_queries: int = 50
    max_pages_per_spider: int = 3
    sources: list[str] | None = None
    skip_enrich: bool = False
    skip_score: bool = False


@router.post("/pipeline/start")
async def start_pipeline(request: PipelineRequest):
    """Start a lead discovery pipeline. Returns run_id for SSE tracking."""
    run_id = await pipeline.run(
        query=request.query,
        max_queries=request.max_queries,
        max_pages_per_spider=request.max_pages_per_spider,
        sources=request.sources,
        skip_enrich=request.skip_enrich,
        skip_score=request.skip_score,
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
async def expand_query(query: str = Query(..., min_length=1)):
    """Preview search query expansion without running crawls."""
    variations = expander.expand(query, max_queries=100)
    return {
        "query": query,
        "total_variations": len(variations),
        "variations": variations[:50],  # Return first 50 for preview
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
