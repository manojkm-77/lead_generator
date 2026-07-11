"""
BuyerHunter AI — CRM Service

Manages leads, pipeline, notes, tags, activities, and sales tracking.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.lead import Lead
from backend.models.note import Note
from backend.models.tag import Tag, LeadTag
from backend.models.activity import Activity
from backend.models.attachment import Attachment
from backend.models.salesperson import Salesperson
from backend.models.company import Company

logger = logging.getLogger(__name__)

VALID_STATUSES = ["cold", "warm", "hot", "interested", "negotiation", "won", "lost"]
VALID_PRIORITIES = ["low", "medium", "high", "urgent"]


class CRMService:
    """CRM operations for lead management."""

    # ── Leads ─────────────────────────────────────────────────────────────────

    async def create_lead(self, db: AsyncSession, data: dict) -> Lead:
        lead = Lead(**data)
        db.add(lead)
        await db.flush()

        # Log activity
        await self.log_activity(db, lead.id, "created", "Lead created")
        await db.commit()
        await db.refresh(lead)
        return lead

    async def get_lead(self, db: AsyncSession, lead_id: int) -> Lead | None:
        result = await db.execute(
            select(Lead)
            .options(
                selectinload(Lead.company),
                selectinload(Lead.salesperson),
                selectinload(Lead.notes),
                selectinload(Lead.tags).selectinload(LeadTag.tag),
                selectinload(Lead.activities),
                selectinload(Lead.attachments),
            )
            .where(Lead.id == lead_id)
        )
        return result.scalar_one_or_none()

    async def update_lead(self, db: AsyncSession, lead_id: int, data: dict) -> Lead | None:
        lead = await db.get(Lead, lead_id)
        if not lead:
            return None

        old_status = lead.status
        for key, value in data.items():
            if value is not None and hasattr(lead, key):
                setattr(lead, key, value)

        # Log status change
        if data.get("status") and data["status"] != old_status:
            await self.log_activity(
                db, lead_id, "status_change",
                f"Status changed: {old_status} → {data['status']}"
            )

        # Log assignment
        if data.get("salesperson_id") and data["salesperson_id"] != lead.salesperson_id:
            await self.log_activity(
                db, lead_id, "assignment",
                f"Assigned to salesperson #{data['salesperson_id']}"
            )

        await db.commit()
        await db.refresh(lead)
        return lead

    async def delete_lead(self, db: AsyncSession, lead_id: int) -> bool:
        lead = await db.get(Lead, lead_id)
        if not lead:
            return False
        await db.delete(lead)
        await db.commit()
        return True

    async def list_leads(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        salesperson_id: int | None = None,
        priority: str | None = None,
        search: str | None = None,
        tag: str | None = None,
        has_followup: bool | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[Lead], int]:
        query = (
            select(Lead)
            .options(
                selectinload(Lead.company),
                selectinload(Lead.salesperson),
                selectinload(Lead.tags).selectinload(LeadTag.tag),
            )
        )
        count_query = select(func.count(Lead.id))

        if status:
            query = query.where(Lead.status == status)
            count_query = count_query.where(Lead.status == status)
        if salesperson_id:
            query = query.where(Lead.salesperson_id == salesperson_id)
            count_query = count_query.where(Lead.salesperson_id == salesperson_id)
        if priority:
            query = query.where(Lead.priority == priority)
            count_query = count_query.where(Lead.priority == priority)
        if search:
            query = query.join(Lead.company).where(
                Company.company_name.ilike(f"%{search}%")
            )
            count_query = count_query.join(Company).where(
                Company.company_name.ilike(f"%{search}%")
            )
        if has_followup:
            query = query.where(Lead.next_followup.isnot(None))
            count_query = count_query.where(Lead.next_followup.isnot(None))

        total = (await db.execute(count_query)).scalar() or 0

        sort_col = getattr(Lead, sort_by, Lead.updated_at)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        leads = list(result.scalars().all())

        return leads, total

    async def get_pipeline_stats(self, db: AsyncSession) -> dict:
        total = (await db.execute(select(func.count(Lead.id)))).scalar() or 0

        # By status
        status_result = await db.execute(
            select(Lead.status, func.count(Lead.id)).group_by(Lead.status)
        )
        by_status = {row[0]: row[1] for row in status_result.all()}
        for s in VALID_STATUSES:
            by_status.setdefault(s, 0)

        # Deal values
        total_value = (await db.execute(
            select(func.sum(Lead.deal_value)).where(Lead.deal_value.isnot(None))
        )).scalar() or 0

        avg_value = (await db.execute(
            select(func.avg(Lead.deal_value)).where(Lead.deal_value.isnot(None))
        )).scalar() or 0

        # Conversion rate (won / total)
        won = by_status.get("won", 0)
        conversion = round(won / total * 100, 1) if total > 0 else 0

        # Follow-ups
        now = datetime.now(timezone.utc)
        overdue = (await db.execute(
            select(func.count(Lead.id)).where(
                Lead.next_followup.isnot(None),
                Lead.next_followup < now,
                Lead.status.notin_(["won", "lost"]),
            )
        )).scalar() or 0

        upcoming = (await db.execute(
            select(func.count(Lead.id)).where(
                Lead.next_followup.isnot(None),
                Lead.next_followup >= now,
                Lead.next_followup <= now + timedelta(days=7),
                Lead.status.notin_(["won", "lost"]),
            )
        )).scalar() or 0

        return {
            "total_leads": total,
            "by_status": by_status,
            "total_value": total_value,
            "conversion_rate": conversion,
            "avg_deal_value": int(avg_value),
            "overdue_followups": overdue,
            "upcoming_followups": upcoming,
        }

    # ── Notes ─────────────────────────────────────────────────────────────────

    async def add_note(self, db: AsyncSession, lead_id: int, content: str, created_by: str = None) -> Note:
        note = Note(lead_id=lead_id, content=content, created_by=created_by)
        db.add(note)
        await self.log_activity(db, lead_id, "note", f"Note added: {content[:50]}...")
        await db.commit()
        await db.refresh(note)
        return note

    async def get_notes(self, db: AsyncSession, lead_id: int) -> list[Note]:
        result = await db.execute(
            select(Note).where(Note.lead_id == lead_id).order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete_note(self, db: AsyncSession, note_id: int) -> bool:
        note = await db.get(Note, note_id)
        if not note:
            return False
        await db.delete(note)
        await db.commit()
        return True

    # ── Tags ──────────────────────────────────────────────────────────────────

    async def create_tag(self, db: AsyncSession, name: str, color: str = "#3b82f6") -> Tag:
        tag = Tag(name=name, color=color)
        db.add(tag)
        await db.commit()
        await db.refresh(tag)
        return tag

    async def list_tags(self, db: AsyncSession) -> list[Tag]:
        result = await db.execute(select(Tag).order_by(Tag.name))
        return list(result.scalars().all())

    async def add_tag_to_lead(self, db: AsyncSession, lead_id: int, tag_id: int) -> bool:
        existing = await db.execute(
            select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id)
        )
        if existing.scalar_one_or_none():
            return False
        db.add(LeadTag(lead_id=lead_id, tag_id=tag_id))
        await db.commit()
        return True

    async def remove_tag_from_lead(self, db: AsyncSession, lead_id: int, tag_id: int) -> bool:
        result = await db.execute(
            select(LeadTag).where(LeadTag.lead_id == lead_id, LeadTag.tag_id == tag_id)
        )
        lt = result.scalar_one_or_none()
        if not lt:
            return False
        await db.delete(lt)
        await db.commit()
        return True

    async def delete_tag(self, db: AsyncSession, tag_id: int) -> bool:
        tag = await db.get(Tag, tag_id)
        if not tag:
            return False
        await db.delete(tag)
        await db.commit()
        return True

    # ── Activities ────────────────────────────────────────────────────────────

    async def log_activity(self, db: AsyncSession, lead_id: int, activity_type: str, title: str = None, description: str = None, created_by: str = None):
        activity = Activity(
            lead_id=lead_id,
            activity_type=activity_type,
            title=title,
            description=description,
            created_by=created_by,
        )
        db.add(activity)
        return activity

    async def get_activities(self, db: AsyncSession, lead_id: int, limit: int = 50) -> list[Activity]:
        result = await db.execute(
            select(Activity)
            .where(Activity.lead_id == lead_id)
            .order_by(Activity.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def record_call(self, db: AsyncSession, lead_id: int, notes: str = None, created_by: str = None):
        lead = await db.get(Lead, lead_id)
        if lead:
            lead.last_contacted = datetime.now(timezone.utc)
        await self.log_activity(db, lead_id, "call", "Phone call", notes, created_by)
        await db.commit()

    async def record_email(self, db: AsyncSession, lead_id: int, subject: str = None, created_by: str = None):
        lead = await db.get(Lead, lead_id)
        if lead:
            lead.last_contacted = datetime.now(timezone.utc)
        await self.log_activity(db, lead_id, "email", f"Email sent: {subject}", None, created_by)
        await db.commit()

    async def record_meeting(self, db: AsyncSession, lead_id: int, notes: str = None, created_by: str = None):
        lead = await db.get(Lead, lead_id)
        if lead:
            lead.last_contacted = datetime.now(timezone.utc)
        await self.log_activity(db, lead_id, "meeting", "Meeting", notes, created_by)
        await db.commit()

    # ── Salesperson ───────────────────────────────────────────────────────────

    async def create_salesperson(self, db: AsyncSession, data: dict) -> Salesperson:
        sp = Salesperson(**data)
        db.add(sp)
        await db.commit()
        await db.refresh(sp)
        return sp

    async def list_salespeople(self, db: AsyncSession) -> list[Salesperson]:
        result = await db.execute(
            select(Salesperson).where(Salesperson.is_active == True).order_by(Salesperson.name)
        )
        return list(result.scalars().all())

    async def delete_salesperson(self, db: AsyncSession, sp_id: int) -> bool:
        sp = await db.get(Salesperson, sp_id)
        if not sp:
            return False
        sp.is_active = False
        await db.commit()
        return True

    # ── Bulk Operations ───────────────────────────────────────────────────────

    async def convert_company_to_lead(self, db: AsyncSession, company_id: int, salesperson_id: int = None) -> Lead:
        """Convert an existing company into a CRM lead."""
        existing = await db.execute(
            select(Lead).where(Lead.company_id == company_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Company already has a lead")

        company = await db.get(Company, company_id)
        if not company:
            raise ValueError("Company not found")

        # Derive initial stage from company score (not hardcoded Cold)
        score = company.lead_score or 0
        if score >= 80:
            initial_status = "hot"
        elif score >= 60:
            initial_status = "warm"
        elif score >= 40:
            initial_status = "interested"
        else:
            initial_status = "cold"

        lead = Lead(
            company_id=company_id,
            salesperson_id=salesperson_id,
            status=initial_status,
        )
        db.add(lead)
        await db.flush()
        await self.log_activity(db, lead.id, "created", f"Lead created from company: {company.company_name} (score={score}, stage={initial_status})")
        await db.commit()
        await db.refresh(lead)
        return lead

    async def bulk_update_status(self, db: AsyncSession, lead_ids: list[int], status: str) -> int:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}")

        count = 0
        for lead_id in lead_ids:
            lead = await db.get(Lead, lead_id)
            if lead:
                old = lead.status
                lead.status = status
                await self.log_activity(db, lead_id, "status_change", f"Status: {old} → {status}")
                count += 1

        await db.commit()
        return count
