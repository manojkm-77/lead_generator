"""
BuyerHunter AI — Lead Enrichment Service

Orchestrates website crawling + AI analysis to enrich company leads.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone

from backend.database import async_session
from backend.models.company import Company
from backend.services.website_enricher import WebsiteEnricher, EnrichmentData
from backend.services.ai_qualifier import AIQualifier

logger = logging.getLogger(__name__)


class EnrichmentService:
    """Enriches company leads with website data and AI scoring."""

    def __init__(self):
        self.enricher = WebsiteEnricher()
        self.qualifier = AIQualifier()

    async def enrich_company(self, company_id: int) -> dict:
        """Enrich a single company by ID."""
        async with async_session() as db:
            company = await db.get(Company, company_id)
            if not company:
                return {"status": "error", "message": "Company not found"}

            if not company.website:
                return {"status": "skipped", "message": "No website to enrich"}

            result = await self._enrich_and_classify(company)

            # Update company record
            for key, value in result.items():
                if hasattr(company, key) and value is not None:
                    setattr(company, key, value)

            company.enriched_at = datetime.now(timezone.utc)
            await db.commit()

            return {
                "status": "completed",
                "company_id": company.id,
                "company_name": company.company_name,
                "lead_score": company.lead_score,
                "industry": company.industry,
            }

    async def enrich_batch(self, limit: int = 50, min_score: int = 0) -> dict:
        """Enrich multiple companies that haven't been enriched yet."""
        async with async_session() as db:
            query = (
                Company.__table__.select()
                .where(
                    Company.website.isnot(None),
                    Company.website != "",
                    Company.enriched_at.is_(None),
                    Company.lead_score <= min_score,
                )
                .limit(limit)
            )
            result = await db.execute(query)
            companies_data = result.fetchall()

            if not companies_data:
                return {"status": "completed", "enriched": 0, "message": "No companies to enrich"}

            enriched = 0
            errors = 0

            for row in companies_data:
                company = await db.get(Company, row.id)
                if not company:
                    continue

                try:
                    result = await self._enrich_and_classify(company)

                    for key, value in result.items():
                        if hasattr(company, key) and value is not None:
                            setattr(company, key, value)

                    company.enriched_at = datetime.now(timezone.utc)
                    enriched += 1

                    logger.info(
                        f"[{enriched}/{len(companies_data)}] Enriched: {company.company_name} "
                        f"(score={company.lead_score})"
                    )

                except Exception as e:
                    errors += 1
                    logger.error(f"Failed to enrich {company.company_name}: {e}")

                # Rate limit between enrichments
                await asyncio.sleep(1.0)

            await db.commit()

            return {
                "status": "completed",
                "enriched": enriched,
                "errors": errors,
                "total": len(companies_data),
            }

    async def _enrich_and_classify(self, company: Company) -> dict:
        """Crawl website and classify with AI."""
        website_data = await self.enricher.enrich(company.website)

        # Merge website data with company data
        enrichment_dict = self._merge_data(company, website_data)

        # Run AI classification with enriched data
        classification = await self.qualifier.classify(enrichment_dict)

        # Merge classification results
        enrichment_dict.update({
            "lead_score": classification.get("lead_score", company.lead_score),
            "industry": classification.get("category", company.industry),
            "ai_reason": classification.get("reason", ""),
            "ai_confidence": classification.get("confidence", 0),
            "ai_consumption": classification.get("consumption_estimate", "Unknown"),
            "ai_frequency": classification.get("buying_frequency", "Unknown"),
            "estimated_size": classification.get("estimated_size", "Unknown"),
            "potential_oil_usage": classification.get("potential_oil_usage", "Unknown"),
            "estimated_annual_consumption": classification.get("estimated_annual_consumption", "Unknown"),
        })

        return enrichment_dict

    def _merge_data(self, company: Company, website_data: EnrichmentData) -> dict:
        """Merge existing company data with website enrichment."""
        # Parse existing products
        existing_products = []
        if company.products:
            try:
                existing_products = json.loads(company.products)
            except json.JSONDecodeError:
                existing_products = [company.products]

        # Merge products from website
        website_products = website_data.products or []
        all_products = list(set(existing_products + website_products))

        return {
            "id": company.id,
            "company_name": company.company_name,
            "website": company.website,
            "phone": company.phone or (website_data.phones[0] if website_data.phones else None),
            "whatsapp": company.whatsapp or (website_data.phones[0] if website_data.phones else None),
            "email": company.email or (website_data.emails[0] if website_data.emails else None),
            "address": company.address or website_data.address,
            "city": company.city or website_data.city,
            "state": company.state or website_data.state,
            "country": company.country,
            "industry": company.industry,
            "products": json.dumps(all_products) if all_products else company.products,
            "about_us": website_data.about_us or "",
            "brands": json.dumps(website_data.brands) if website_data.brands else None,
            "industries_served": json.dumps(website_data.industries_served) if website_data.industries_served else None,
            "company_description": website_data.company_description or "",
            "contact_page": website_data.contact_page or "",
            "careers_page": website_data.careers_page or "",
            "procurement_info": website_data.procurement_info or "",
        }

    async def close(self):
        await self.enricher.close()
