import json
import logging
from rapidfuzz import fuzz

from backend.models.company import Company

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 85


class DeduplicationPipeline:
    def __init__(self):
        self.seen_companies: dict[str, dict] = {}

    def is_duplicate(self, company_data: dict, existing: list[Company]) -> bool:
        name = company_data.get("company_name", "").strip().lower()
        phone = company_data.get("phone", "")

        for existing_company in existing:
            existing_name = existing_company.company_name.strip().lower()
            name_score = fuzz.ratio(name, existing_name)
            if name_score >= SIMILARITY_THRESHOLD:
                if phone and existing_company.phone and phone == existing_company.phone:
                    return True
                if name_score >= 95:
                    return True

        cache_key = name
        if cache_key in self.seen_companies:
            return True
        self.seen_companies[cache_key] = company_data
        return False

    async def process_batch(self, companies: list[dict], db_session) -> list[dict]:
        result = await db_session.execute(
            Company.__table__.select()
        )
        existing = (await db_session.execute(
            Company.__table__.select()
        )).fetchall()

        unique = []
        duplicates = 0
        for company in companies:
            if not self.is_duplicate(company, existing):
                unique.append(company)
            else:
                duplicates += 1

        logger.info(f"Deduplication: {len(companies)} input, {unique.__len__()} unique, {duplicates} duplicates")
        return unique
