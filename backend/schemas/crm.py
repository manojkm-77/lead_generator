from datetime import datetime
from pydantic import BaseModel


class LeadCreate(BaseModel):
    company_id: int
    salesperson_id: int | None = None
    status: str = "cold"
    deal_value: int | None = None
    priority: str = "medium"
    next_followup: datetime | None = None
    followup_notes: str | None = None


class LeadUpdate(BaseModel):
    status: str | None = None
    salesperson_id: int | None = None
    deal_value: int | None = None
    priority: str | None = None
    lost_reason: str | None = None
    next_followup: datetime | None = None
    followup_notes: str | None = None


class LeadRead(BaseModel):
    id: int
    company_id: int
    salesperson_id: int | None = None
    status: str
    deal_value: int | None = None
    priority: str
    lost_reason: str | None = None
    next_followup: datetime | None = None
    last_contacted: datetime | None = None
    followup_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    # Joined fields
    company_name: str | None = None
    company_website: str | None = None
    company_phone: str | None = None
    company_email: str | None = None
    company_city: str | None = None
    company_state: str | None = None
    company_industry: str | None = None
    company_lead_score: int | None = None
    company_products: str | None = None
    salesperson_name: str | None = None
    tags: list[str] = []
    notes_count: int = 0
    activities_count: int = 0

    model_config = {"from_attributes": True}


class LeadList(BaseModel):
    total: int
    page: int
    page_size: int
    leads: list[LeadRead]


class NoteCreate(BaseModel):
    content: str
    created_by: str | None = None


class NoteRead(BaseModel):
    id: int
    lead_id: int
    content: str
    created_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str
    color: str = "#3b82f6"


class TagRead(BaseModel):
    id: int
    name: str
    color: str

    model_config = {"from_attributes": True}


class ActivityRead(BaseModel):
    id: int
    lead_id: int
    activity_type: str
    title: str | None = None
    description: str | None = None
    created_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SalespersonCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None


class SalespersonRead(BaseModel):
    id: int
    name: str
    email: str | None = None
    phone: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class PipelineStats(BaseModel):
    total_leads: int
    by_status: dict[str, int]
    total_value: int
    conversion_rate: float
    avg_deal_value: int
    overdue_followups: int
    upcoming_followups: int
