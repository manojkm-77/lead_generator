"""
BuyerHunter AI — CRM API Routes
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_db
from backend.services.crm import CRMService, VALID_STATUSES
from backend.schemas.crm import (
    LeadCreate, LeadUpdate, LeadRead, LeadList,
    NoteCreate, NoteRead,
    TagCreate, TagRead,
    ActivityRead,
    SalespersonCreate, SalespersonRead,
    PipelineStats,
)

router = APIRouter()
crm = CRMService()


# ── Pipeline Stats ────────────────────────────────────────────────────────────


@router.get("/pipeline/stats", response_model=PipelineStats)
async def pipeline_stats(db: AsyncSession = Depends(get_db)):
    return await crm.get_pipeline_stats(db)


@router.get("/pipeline")
async def pipeline_view(
    status: str | None = None,
    salesperson_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get leads grouped by status for pipeline view."""
    from backend.models.lead import Lead
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from backend.models.tag import LeadTag

    query = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.salesperson),
        selectinload(Lead.tags).selectinload(LeadTag.tag),
    )

    if status:
        query = query.where(Lead.status == status)
    if salesperson_id:
        query = query.where(Lead.salesperson_id == salesperson_id)

    query = query.order_by(Lead.updated_at.desc())
    result = await db.execute(query)
    leads = list(result.scalars().all())

    # Group by status
    pipeline = {}
    for s in VALID_STATUSES:
        pipeline[s] = []

    for lead in leads:
        if lead.status in pipeline:
            pipeline[lead.status].append({
                "id": lead.id,
                "company_name": lead.company.company_name if lead.company else "Unknown",
                "company_city": lead.company.city if lead.company else None,
                "company_industry": lead.company.industry if lead.company else None,
                "company_lead_score": lead.company.lead_score if lead.company else 0,
                "deal_value": lead.deal_value,
                "priority": lead.priority,
                "next_followup": lead.next_followup.isoformat() if lead.next_followup else None,
                "salesperson_name": lead.salesperson.name if lead.salesperson else None,
                "tags": [{"name": lt.tag.name, "color": lt.tag.color} for lt in lead.tags],
                "updated_at": lead.updated_at.isoformat(),
            })

    return pipeline


# ── Leads ─────────────────────────────────────────────────────────────────────


@router.get("/leads", response_model=LeadList)
async def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    salesperson_id: int | None = None,
    priority: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    has_followup: bool | None = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    db: AsyncSession = Depends(get_db),
):
    leads, total = await crm.list_leads(
        db, page, page_size, status, salesperson_id,
        priority, search, tag, has_followup, sort_by, sort_order,
    )

    lead_reads = []
    for lead in leads:
        lr = LeadRead(
            id=lead.id,
            company_id=lead.company_id,
            salesperson_id=lead.salesperson_id,
            status=lead.status,
            deal_value=lead.deal_value,
            priority=lead.priority,
            lost_reason=lead.lost_reason,
            next_followup=lead.next_followup,
            last_contacted=lead.last_contacted,
            followup_notes=lead.followup_notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at,
            company_name=lead.company.company_name if lead.company else None,
            company_website=lead.company.website if lead.company else None,
            company_phone=lead.company.phone if lead.company else None,
            company_email=lead.company.email if lead.company else None,
            company_city=lead.company.city if lead.company else None,
            company_state=lead.company.state if lead.company else None,
            company_industry=lead.company.industry if lead.company else None,
            company_lead_score=lead.company.lead_score if lead.company else None,
            company_products=lead.company.products if lead.company else None,
            salesperson_name=lead.salesperson.name if lead.salesperson else None,
            tags=[lt.tag.name for lt in lead.tags],
            notes_count=len(lead.notes) if hasattr(lead, "notes") and lead.notes else 0,
            activities_count=len(lead.activities) if hasattr(lead, "activities") and lead.activities else 0,
        )
        lead_reads.append(lr)

    return LeadList(total=total, page=page, page_size=page_size, leads=lead_reads)


@router.post("/leads", response_model=LeadRead)
async def create_lead(data: LeadCreate, db: AsyncSession = Depends(get_db)):
    try:
        lead = await crm.create_lead(db, data.model_dump())
        return await _lead_to_read(db, lead)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leads/{lead_id}/convert")
async def convert_to_lead(lead_id: int, salesperson_id: int = None, db: AsyncSession = Depends(get_db)):
    """Convert a company to a lead (by company_id)."""
    try:
        lead = await crm.convert_company_to_lead(db, lead_id, salesperson_id)
        return {"status": "created", "lead_id": lead.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leads/bulk-status")
async def bulk_update_status(lead_ids: list[int], status: str, db: AsyncSession = Depends(get_db)):
    try:
        count = await crm.bulk_update_status(db, lead_ids, status)
        return {"updated": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leads/{lead_id}", response_model=LeadRead)
async def get_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    lead = await crm.get_lead(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await _lead_to_read(db, lead)


@router.put("/leads/{lead_id}", response_model=LeadRead)
async def update_lead(lead_id: int, data: LeadUpdate, db: AsyncSession = Depends(get_db)):
    lead = await crm.update_lead(db, lead_id, data.model_dump(exclude_unset=True))
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await _lead_to_read(db, lead)


@router.delete("/leads/{lead_id}")
async def delete_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    if not await crm.delete_lead(db, lead_id):
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "deleted"}


# ── Notes ─────────────────────────────────────────────────────────────────────


@router.get("/leads/{lead_id}/notes", response_model=list[NoteRead])
async def get_notes(lead_id: int, db: AsyncSession = Depends(get_db)):
    return await crm.get_notes(db, lead_id)


@router.post("/leads/{lead_id}/notes", response_model=NoteRead)
async def add_note(lead_id: int, data: NoteCreate, db: AsyncSession = Depends(get_db)):
    return await crm.add_note(db, lead_id, data.content, data.created_by)


@router.delete("/notes/{note_id}")
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db)):
    if not await crm.delete_note(db, note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"status": "deleted"}


# ── Tags ──────────────────────────────────────────────────────────────────────


@router.get("/tags", response_model=list[TagRead])
async def list_tags(db: AsyncSession = Depends(get_db)):
    return await crm.list_tags(db)


@router.post("/tags", response_model=TagRead)
async def create_tag(data: TagCreate, db: AsyncSession = Depends(get_db)):
    return await crm.create_tag(db, data.name, data.color)


@router.delete("/tags/{tag_id}")
async def delete_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    if not await crm.delete_tag(db, tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted"}


@router.post("/leads/{lead_id}/tags/{tag_id}")
async def add_tag(lead_id: int, tag_id: int, db: AsyncSession = Depends(get_db)):
    added = await crm.add_tag_to_lead(db, lead_id, tag_id)
    return {"added": added}


@router.delete("/leads/{lead_id}/tags/{tag_id}")
async def remove_tag(lead_id: int, tag_id: int, db: AsyncSession = Depends(get_db)):
    removed = await crm.remove_tag_from_lead(db, lead_id, tag_id)
    return {"removed": removed}


# ── Activities ────────────────────────────────────────────────────────────────


@router.get("/leads/{lead_id}/activities", response_model=list[ActivityRead])
async def get_activities(lead_id: int, limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await crm.get_activities(db, lead_id, limit)


@router.post("/leads/{lead_id}/call")
async def record_call(lead_id: int, notes: str = None, created_by: str = None, db: AsyncSession = Depends(get_db)):
    await crm.record_call(db, lead_id, notes, created_by)
    return {"status": "recorded"}


@router.post("/leads/{lead_id}/email")
async def record_email(lead_id: int, subject: str = None, created_by: str = None, db: AsyncSession = Depends(get_db)):
    await crm.record_email(db, lead_id, subject, created_by)
    return {"status": "recorded"}


@router.post("/leads/{lead_id}/meeting")
async def record_meeting(lead_id: int, notes: str = None, created_by: str = None, db: AsyncSession = Depends(get_db)):
    await crm.record_meeting(db, lead_id, notes, created_by)
    return {"status": "recorded"}


# ── Salespeople ───────────────────────────────────────────────────────────────


@router.get("/salespeople", response_model=list[SalespersonRead])
async def list_salespeople(db: AsyncSession = Depends(get_db)):
    return await crm.list_salespeople(db)


@router.post("/salespeople", response_model=SalespersonRead)
async def create_salesperson(data: SalespersonCreate, db: AsyncSession = Depends(get_db)):
    return await crm.create_salesperson(db, data.model_dump())


@router.delete("/salespeople/{sp_id}")
async def delete_salesperson(sp_id: int, db: AsyncSession = Depends(get_db)):
    if not await crm.delete_salesperson(db, sp_id):
        raise HTTPException(status_code=404, detail="Salesperson not found")
    return {"status": "deleted"}


# ── Helper ────────────────────────────────────────────────────────────────────


async def _lead_to_read(db: AsyncSession, lead) -> LeadRead:
    if hasattr(lead, "company") and lead.company:
        company = lead.company
    else:
        company = await db.get(__import__("backend.models.company", fromlist=["Company"]).Company, lead.company_id)

    sp_name = None
    if hasattr(lead, "salesperson") and lead.salesperson:
        sp_name = lead.salesperson.name
    elif lead.salesperson_id:
        sp = await db.get(__import__("backend.models.salesperson", fromlist=["Salesperson"]).Salesperson, lead.salesperson_id)
        sp_name = sp.name if sp else None

    tags = []
    if hasattr(lead, "tags") and lead.tags:
        tags = [lt.tag.name for lt in lead.tags]

    return LeadRead(
        id=lead.id,
        company_id=lead.company_id,
        salesperson_id=lead.salesperson_id,
        status=lead.status,
        deal_value=lead.deal_value,
        priority=lead.priority,
        lost_reason=lead.lost_reason,
        next_followup=lead.next_followup,
        last_contacted=lead.last_contacted,
        followup_notes=lead.followup_notes,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
        company_name=company.company_name if company else None,
        company_website=company.website if company else None,
        company_phone=company.phone if company else None,
        company_email=company.email if company else None,
        company_city=company.city if company else None,
        company_state=company.state if company else None,
        company_industry=company.industry if company else None,
        company_lead_score=company.lead_score if company else None,
        company_products=company.products if company else None,
        salesperson_name=sp_name,
        tags=tags,
    )
