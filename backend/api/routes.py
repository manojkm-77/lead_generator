import os
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.models.company import Company
from backend.schemas.company import CompanyCreate, CompanyRead, CompanyList
from backend.schemas.crawl import CrawlRequest, CrawlLogRead
from backend.services.spider_manager import SpiderManager
from backend.services.stats import get_dashboard_stats, get_crawl_logs
from backend.services.export import export_csv, export_excel, export_json
from backend.services.ai_qualifier import AIQualifier

router = APIRouter()
spider_manager = SpiderManager()


# ── Dashboard ─────────────────────────────────────────────────────────────────


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    return await get_dashboard_stats(db)


# ── Global Search ─────────────────────────────────────────────────────────────


@router.get("/search")
async def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Global search across companies, products, GST, IEC, email, phone, website, state, city."""
    like = f"%{q}%"
    query = select(Company).where(
        or_(
            Company.company_name.ilike(like),
            Company.products.ilike(like),
            Company.gst_number.ilike(like),
            Company.iec_code.ilike(like),
            Company.cin_number.ilike(like),
            Company.email.ilike(like),
            Company.phone.ilike(like),
            Company.website.ilike(like),
            Company.state.ilike(like),
            Company.city.ilike(like),
            Company.industry.ilike(like),
            Company.about_us.ilike(like),
            Company.company_description.ilike(like),
            Company.district.ilike(like),
        )
    ).order_by(Company.lead_score.desc()).limit(limit)

    result = await db.execute(query)
    companies = [CompanyRead.model_validate(row) for row in result.scalars().all()]

    return {"total": len(companies), "query": q, "results": companies}


# ── Companies ─────────────────────────────────────────────────────────────────


@router.get("/companies", response_model=CompanyList)
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    city: str | None = None,
    state: str | None = None,
    industry: str | None = None,
    source: str | None = None,
    min_score: int | None = None,
    max_score: int | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    is_importer: bool | None = None,
    is_exporter: bool | None = None,
    is_manufacturer: bool | None = None,
    is_distributor: bool | None = None,
    is_wholesaler: bool | None = None,
    has_website: bool | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    query = select(Company)
    count_query = select(func.count(Company.id))

    filters = []
    if search:
        like = f"%{search}%"
        search_filter = or_(
            Company.company_name.ilike(like),
            Company.products.ilike(like),
            Company.gst_number.ilike(like),
            Company.iec_code.ilike(like),
            Company.email.ilike(like),
            Company.phone.ilike(like),
            Company.state.ilike(like),
            Company.city.ilike(like),
            Company.industry.ilike(like),
        )
        filters.append(search_filter)
    if city:
        filters.append(Company.city == city)
    if state:
        filters.append(Company.state == state)
    if industry:
        filters.append(Company.industry == industry)
    if source:
        filters.append(Company.source == source)
    if min_score is not None:
        filters.append(Company.lead_score >= min_score)
    if max_score is not None:
        filters.append(Company.lead_score <= max_score)
    if has_email:
        filters.append(Company.email.isnot(None))
        filters.append(Company.email != "")
    if has_phone:
        filters.append(Company.phone.isnot(None))
        filters.append(Company.phone != "")
    if is_importer is not None:
        filters.append(Company.is_importer == is_importer)
    if is_exporter is not None:
        filters.append(Company.is_exporter == is_exporter)
    if is_manufacturer is not None:
        filters.append(Company.is_manufacturer == is_manufacturer)
    if is_distributor is not None:
        filters.append(Company.is_distributor == is_distributor)
    if is_wholesaler is not None:
        filters.append(Company.is_wholesaler == is_wholesaler)
    if has_website:
        filters.append(Company.website.isnot(None))
        filters.append(Company.website != "")

    for f in filters:
        query = query.where(f)
        count_query = count_query.where(f)

    total = (await db.execute(count_query)).scalar() or 0

    sort_col = getattr(Company, sort_by, Company.created_at)
    query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    companies = [CompanyRead.model_validate(row) for row in result.scalars().all()]

    return CompanyList(total=total, page=page, page_size=page_size, companies=companies)


@router.get("/company/{company_id}")
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyRead.model_validate(company)


@router.get("/company/{company_id}/contacts")
async def get_company_contacts(company_id: int, db: AsyncSession = Depends(get_db)):
    from backend.models.contact import Contact
    result = await db.execute(
        select(Contact).where(Contact.company_id == company_id)
        .order_by(Contact.confidence_score.desc())
    )
    contacts = []
    for row in result.scalars().all():
        contacts.append({
            "id": row.id,
            "person_name": row.person_name,
            "designation": row.designation,
            "department": row.department,
            "email": row.email,
            "phone": row.phone,
            "linkedin_url": row.linkedin_url,
            "confidence_score": row.confidence_score,
            "source": row.source,
            "is_verified": row.is_verified,
        })
    return {"total": len(contacts), "contacts": contacts}


# ── Products ──────────────────────────────────────────────────────────────────


@router.get("/products")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Extract all unique products from companies."""
    query = select(Company.products).where(Company.products.isnot(None), Company.products != "")
    if search:
        query = query.where(Company.products.ilike(f"%{search}%"))
    result = await db.execute(query)

    all_products = set()
    for row in result.scalars().all():
        try:
            import json
            items = json.loads(row)
            if isinstance(items, list):
                all_products.update(items)
        except (json.JSONDecodeError, TypeError):
            all_products.add(row)

    sorted_products = sorted(all_products)
    total = len(sorted_products)
    start = (page - 1) * page_size
    paginated = sorted_products[start:start + page_size]

    return {"total": total, "page": page, "page_size": page_size, "products": paginated}


# ── Crawl ─────────────────────────────────────────────────────────────────────


@router.post("/crawl")
async def start_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(
            spider_manager.run_spider,
            request.spider_name,
            request.keywords,
            request.max_pages,
        )
        return {
            "status": "started",
            "spider": request.spider_name,
            "message": f"Crawl job queued for {request.spider_name}",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/crawl/multi")
async def start_multi_crawl(
    spiders: list[str],
    queries: list[str] = None,
    max_pages: int = 5,
    parallel: bool = False,
    background_tasks: BackgroundTasks = None,
):
    invalid = [s for s in spiders if s not in SpiderManager.SPIDER_REGISTRY]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown spiders: {invalid}")
    background_tasks.add_task(spider_manager.run_multiple, spiders, queries, max_pages, parallel)
    return {"status": "started", "spiders": spiders, "message": f"Queued {len(spiders)} spiders"}


@router.post("/crawl/all")
async def start_all_crawls(
    queries: list[str] = None,
    max_pages: int = 3,
    background_tasks: BackgroundTasks = None,
):
    background_tasks.add_task(spider_manager.run_all, queries, max_pages)
    return {"status": "started", "message": "Queued all spiders"}


@router.get("/crawl/status")
async def crawl_status():
    return {"running": spider_manager.get_running(), "interrupted": spider_manager.resume_interrupted()}


@router.get("/spiders")
async def available_spiders():
    return {"spiders": spider_manager.available_spiders(), "types": spider_manager.get_spider_types()}


@router.get("/crawl-logs")
async def crawl_logs(limit: int = Query(20, ge=1, le=100), db: AsyncSession = Depends(get_db)):
    return await get_crawl_logs(db, limit)


# ── Classification & Enrichment ───────────────────────────────────────────────


@router.post("/classify")
async def classify_leads(
    min_score: int = Query(0, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company).where(Company.lead_score < min_score).limit(limit)
    result = await db.execute(query)
    companies = result.scalars().all()
    if not companies:
        return {"message": "No companies to classify", "count": 0}

    qualifier = AIQualifier()
    company_dicts = [
        {"id": c.id, "company_name": c.company_name, "website": c.website,
         "industry": c.industry, "products": c.products, "city": c.city,
         "state": c.state, "country": c.country}
        for c in companies
    ]
    classified = await qualifier.classify_batch(company_dicts)

    updated = 0
    for data in classified:
        company = await db.get(Company, data["id"])
        if company:
            company.lead_score = data.get("lead_score", company.lead_score)
            company.industry = data.get("industry", company.industry)
            company.ai_reason = data.get("ai_reason", "")
            company.ai_confidence = data.get("ai_confidence", 0)
            company.ai_consumption = data.get("ai_consumption", "Unknown")
            company.ai_frequency = data.get("ai_frequency", "Unknown")
            updated += 1
    await db.commit()
    return {"message": f"Classified {updated} companies", "count": updated}


@router.post("/enrich/{company_id}")
async def enrich_company(company_id: int, background_tasks: BackgroundTasks):
    from backend.services.enrichment import EnrichmentService
    service = EnrichmentService()
    background_tasks.add_task(service.enrich_company, company_id)
    return {"status": "started", "company_id": company_id, "message": "Enrichment queued"}


@router.post("/enrich/batch")
async def enrich_batch(
    limit: int = Query(50, ge=1, le=200),
    min_score: int = Query(0, ge=0, le=100),
    background_tasks: BackgroundTasks = None,
):
    from backend.services.enrichment import EnrichmentService
    service = EnrichmentService()
    background_tasks.add_task(service.enrich_batch, limit, min_score)
    return {"status": "started", "limit": limit, "message": f"Batch enrichment queued (up to {limit})"}


@router.get("/enrich/status")
async def enrich_status():
    from backend.database import async_session
    async with async_session() as db:
        total = (await db.execute(select(func.count(Company.id)))).scalar() or 0
        enriched = (await db.execute(
            select(func.count(Company.id)).where(Company.enriched_at.isnot(None))
        )).scalar() or 0
        pending = (await db.execute(
            select(func.count(Company.id)).where(
                Company.website.isnot(None), Company.website != "", Company.enriched_at.is_(None)
            )
        )).scalar() or 0
        return {
            "total_companies": total, "enriched": enriched, "pending": pending,
            "enrichment_rate": round(enriched / total * 100, 1) if total > 0 else 0,
        }


# ── Export ────────────────────────────────────────────────────────────────────


@router.post("/export")
async def export_data(
    format: str = Query("csv"),
    min_score: int | None = None,
    has_email: bool = False,
    has_phone: bool = False,
    source: str | None = None,
    is_importer: bool | None = None,
    is_exporter: bool | None = None,
    state: str | None = None,
    limit: int = Query(1000, ge=1, le=50000),
    db: AsyncSession = Depends(get_db),
):
    query = select(Company)
    if min_score is not None:
        query = query.where(Company.lead_score >= min_score)
    if has_email:
        query = query.where(Company.email.isnot(None), Company.email != "")
    if has_phone:
        query = query.where(Company.phone.isnot(None), Company.phone != "")
    if source:
        query = query.where(Company.source == source)
    if is_importer is not None:
        query = query.where(Company.is_importer == is_importer)
    if is_exporter is not None:
        query = query.where(Company.is_exporter == is_exporter)
    if state:
        query = query.where(Company.state == state)
    query = query.order_by(Company.lead_score.desc()).limit(limit)

    result = await db.execute(query)
    companies = [dict(row._mapping) for row in result.all()]

    if not companies:
        raise HTTPException(status_code=404, detail="No companies to export")

    if format == "csv":
        filepath = export_csv(companies)
    elif format == "excel":
        filepath = export_excel(companies)
    else:
        filepath = export_json(companies)
    return {"filepath": filepath, "count": len(companies), "format": format}


# ── Trade Data ────────────────────────────────────────────────────────────────


@router.post("/import/apeda")
async def import_apeda(background_tasks: BackgroundTasks, year: int | None = None, months: int = 3):
    def _run():
        from import_apeda import APEDADirectoryImporter
        APEDADirectoryImporter().run(from_file=None)
    background_tasks.add_task(_run)
    return {"status": "started", "message": "APEDA import queued"}


@router.post("/import/dgcis")
async def import_dgcis(background_tasks: BackgroundTasks, hs_code: str = "1511", all_years: bool = True):
    def _run():
        from import_dgcis import DGCISImporter
        DGCISImporter().run(hs_code=hs_code, all_years=all_years)
    background_tasks.add_task(_run)
    return {"status": "started", "message": f"DGCIS import queued (HS: {hs_code})"}


@router.get("/trade-data")
async def get_trade_data(hs_code: str | None = None):
    import sqlite3
    conn = sqlite3.connect("buyerhunter.db")
    conn.row_factory = sqlite3.Row
    if hs_code:
        rows = conn.execute("SELECT * FROM trade_data WHERE hs_code = ? ORDER BY year", (hs_code,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM trade_data ORDER BY hs_code, year").fetchall()
    conn.close()
    return [dict(row) for row in rows]


@router.get("/trade-summary")
async def get_trade_summary():
    import sqlite3
    conn = sqlite3.connect("buyerhunter.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT hs_code, year, SUM(value_usd_million) as total_value, SUM(quantity) as total_quantity
        FROM trade_data WHERE value_usd_million > 0
        GROUP BY hs_code, year ORDER BY hs_code, year
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]
