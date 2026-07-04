"""
BuyerHunter AI — Intelligence Engine Orchestrator

Coordinates website analysis, contact discovery, product detection,
buyer scoring, and AI summary generation.
"""

import json
import logging
from datetime import datetime, timezone

from backend.database import async_session
from backend.models.company import Company
from backend.models.intelligence import (
    ProcurementContact, ProductDetection, BuyerScore, BuyerSummary,
)
from backend.services.contact_discovery import ProcurementContactDiscovery
from backend.services.product_detector import ProductDetector
from backend.services.buyer_scorer import BuyerScorer
from backend.services.buyer_summary import BuyerSummaryGenerator

logger = logging.getLogger(__name__)


class IntelligenceEngine:
    """Orchestrates the full buyer intelligence pipeline."""

    def __init__(self):
        self.contact_discovery = ProcurementContactDiscovery()
        self.product_detector = ProductDetector()
        self.buyer_scorer = BuyerScorer()
        self.summary_generator = BuyerSummaryGenerator()

    async def analyze_company(self, company_id: int) -> dict:
        """Run full intelligence analysis on a single company."""
        async with async_session() as db:
            company = await db.get(Company, company_id)
            if not company:
                return {"status": "error", "message": "Company not found"}

            company_data = {
                "id": company.id,
                "company_name": company.company_name,
                "website": company.website,
                "industry": company.industry,
                "products": company.products,
                "about_us": company.about_us,
                "company_description": company.company_description,
                "brands": company.brands,
                "city": company.city,
                "state": company.state,
                "country": company.country,
                "estimated_size": company.estimated_size,
                "lead_score": company.lead_score,
            }

            # 1. Discover procurement contacts
            contacts = []
            if company.website:
                try:
                    contacts = await self.contact_discovery.discover(company.website)
                except Exception as e:
                    logger.error(f"Contact discovery failed: {e}")

            # Store contacts
            for contact in contacts:
                existing = await db.execute(
                    ProcurementContact.__table__.select().where(
                        ProcurementContact.company_id == company_id,
                        ProcurementContact.person_name == contact.name,
                    )
                )
                if not existing.fetchone():
                    db.add(ProcurementContact(
                        company_id=company_id,
                        person_name=contact.name,
                        designation=contact.designation,
                        email=contact.email,
                        phone=contact.phone,
                        linkedin_url=contact.linkedin_url,
                        source_url=contact.source_url,
                        confidence_score=contact.confidence,
                    ))

            # 2. Detect products
            detection_data = self.product_detector.detect(company_data)
            existing_detection = await db.execute(
                ProductDetection.__table__.select().where(ProductDetection.company_id == company_id)
            )
            if existing_detection.fetchone():
                await db.execute(
                    ProductDetection.__table__.update()
                    .where(ProductDetection.company_id == company_id)
                    .values(**{k: v for k, v in detection_data.items() if k != "detection_notes"})
                )
            else:
                db.add(ProductDetection(
                    company_id=company_id,
                    palm_oil=detection_data.get("palm_oil", 0),
                    rbd_palm_olein=detection_data.get("rbd_palm_olein", 0),
                    sunflower_oil=detection_data.get("sunflower_oil", 0),
                    soybean_oil=detection_data.get("soybean_oil", 0),
                    rice_bran_oil=detection_data.get("rice_bran_oil", 0),
                    mustard_oil=detection_data.get("mustard_oil", 0),
                    groundnut_oil=detection_data.get("groundnut_oil", 0),
                    coconut_oil=detection_data.get("coconut_oil", 0),
                    vanaspati=detection_data.get("vanaspati", 0),
                    shortening=detection_data.get("shortening", 0),
                    bakery_fat=detection_data.get("bakery_fat", 0),
                    detection_notes=detection_data.get("detection_notes", ""),
                ))

            # 3. Calculate buyer score
            buyer_metrics = self.buyer_scorer.score(company_data, detection_data, contacts)
            existing_score = await db.execute(
                BuyerScore.__table__.select().where(BuyerScore.company_id == company_id)
            )
            score_data = {
                "monthly_consumption": buyer_metrics.monthly_consumption,
                "annual_consumption": buyer_metrics.annual_consumption,
                "buying_frequency": buyer_metrics.buying_frequency,
                "company_size": buyer_metrics.company_size,
                "manufacturing_capacity": buyer_metrics.manufacturing_capacity,
                "buyer_priority": buyer_metrics.buyer_priority,
                "procurement_maturity": buyer_metrics.procurement_maturity,
                "lead_temperature": buyer_metrics.lead_temperature,
                "buyer_score": buyer_metrics.buyer_score,
                "score_breakdown": json.dumps(buyer_metrics.score_breakdown),
            }
            if existing_score.fetchone():
                await db.execute(
                    BuyerScore.__table__.update()
                    .where(BuyerScore.company_id == company_id)
                    .values(**score_data)
                )
            else:
                db.add(BuyerScore(company_id=company_id, **score_data))

            # 4. Generate AI summary
            try:
                summary_data = await self.summary_generator.generate(
                    company_data, detection_data, score_data
                )
                # Convert list fields to JSON strings for SQLite
                if isinstance(summary_data.get("suggested_products"), list):
                    summary_data["suggested_products"] = json.dumps(summary_data["suggested_products"])
                existing_summary = await db.execute(
                    BuyerSummary.__table__.select().where(BuyerSummary.company_id == company_id)
                )
                if existing_summary.fetchone():
                    await db.execute(
                        BuyerSummary.__table__.update()
                        .where(BuyerSummary.company_id == company_id)
                        .values(**{k: v for k, v in summary_data.items() if k != "company_id"})
                    )
                else:
                    db.add(BuyerSummary(company_id=company_id, **{
                        k: v for k, v in summary_data.items() if k != "company_id"
                    }))
            except Exception as e:
                logger.error(f"Summary generation failed: {e}")

            # Update company score
            company.lead_score = buyer_metrics.buyer_score
            company.estimated_size = buyer_metrics.company_size
            company.potential_oil_usage = buyer_metrics.lead_temperature
            company.estimated_annual_consumption = buyer_metrics.annual_consumption
            company.enriched_at = datetime.now(timezone.utc)

            await db.commit()

            return {
                "status": "completed",
                "company_id": company_id,
                "company_name": company.company_name,
                "buyer_score": buyer_metrics.buyer_score,
                "buyer_priority": buyer_metrics.buyer_priority,
                "contacts_found": len(contacts),
                "products_detected": sum(1 for k, v in detection_data.items() if k != "detection_notes" and v >= 0.3),
            }

    async def analyze_batch(self, limit: int = 50, min_score: int = 0) -> dict:
        """Analyze multiple companies."""
        async with async_session() as db:
            query = (
                Company.__table__.select()
                .where(
                    Company.website.isnot(None),
                    Company.website != "",
                    Company.lead_score <= min_score,
                )
                .limit(limit)
            )
            result = await db.execute(query)
            companies = result.fetchall()

            if not companies:
                return {"status": "completed", "analyzed": 0, "message": "No companies to analyze"}

        analyzed = 0
        errors = 0
        for row in companies:
            try:
                result = await self.analyze_company(row.id)
                if result.get("status") == "completed":
                    analyzed += 1
                    logger.info(f"[{analyzed}/{len(companies)}] Analyzed: {result.get('company_name')} (score={result.get('buyer_score')})")
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.error(f"Analysis failed for company {row.id}: {e}")

        return {
            "status": "completed",
            "analyzed": analyzed,
            "errors": errors,
            "total": len(companies),
        }

    async def get_intelligence(self, company_id: int) -> dict:
        """Get full intelligence data for a company."""
        async with async_session() as db:
            company = await db.get(Company, company_id)
            if not company:
                return None

            # Get contacts
            contacts_result = await db.execute(
                ProcurementContact.__table__.select()
                .where(ProcurementContact.company_id == company_id)
                .order_by(ProcurementContact.confidence_score.desc())
            )
            contacts = [dict(r._mapping) for r in contacts_result.fetchall()]

            # Get product detection
            detection_result = await db.execute(
                ProductDetection.__table__.select()
                .where(ProductDetection.company_id == company_id)
            )
            detection_row = detection_result.fetchone()
            detection = dict(detection_row._mapping) if detection_row else None

            # Get buyer score
            score_result = await db.execute(
                BuyerScore.__table__.select()
                .where(BuyerScore.company_id == company_id)
            )
            score_row = score_result.fetchone()
            score = dict(score_row._mapping) if score_row else None

            # Get summary
            summary_result = await db.execute(
                BuyerSummary.__table__.select()
                .where(BuyerSummary.company_id == company_id)
            )
            summary_row = summary_result.fetchone()
            summary = dict(summary_row._mapping) if summary_row else None

            return {
                "company": {
                    "id": company.id,
                    "name": company.company_name,
                    "website": company.website,
                    "industry": company.industry,
                    "city": company.city,
                    "state": company.state,
                    "lead_score": company.lead_score,
                },
                "contacts": contacts,
                "product_detection": detection,
                "buyer_score": score,
                "summary": summary,
            }

    async def get_top_buyers(self, limit: int = 100) -> list[dict]:
        """Get top scoring buyers."""
        async with async_session() as db:
            result = await db.execute(
                Company.__table__.select()
                .where(Company.lead_score > 0)
                .order_by(Company.lead_score.desc())
                .limit(limit)
            )
            return [dict(r._mapping) for r in result.fetchall()]

    async def get_procurement_contacts(self, limit: int = 100) -> list[dict]:
        """Get all discovered procurement contacts."""
        async with async_session() as db:
            result = await db.execute(
                ProcurementContact.__table__.select()
                .order_by(ProcurementContact.confidence_score.desc())
                .limit(limit)
            )
            contacts = [dict(r._mapping) for r in result.fetchall()]

            # Enrich with company names
            for contact in contacts:
                company = await db.get(Company, contact["company_id"])
                contact["company_name"] = company.company_name if company else "Unknown"

            return contacts

    async def close(self):
        await self.contact_discovery.close()
