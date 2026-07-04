"""
BuyerHunter AI — Lead Enrichment Script

Deep-crawls company websites and uses AI to enrich lead data.

Usage:
    python enrich_leads.py                     # Enrich all unprocessed leads
    python enrich_leads.py --limit 20          # Enrich up to 20 companies
    python enrich_leads.py --company-id 123    # Enrich a specific company
    python enrich_leads.py --min-score 50      # Enrich companies with score < 50
"""

import argparse
import asyncio
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("buyerhunter.enrichment")

DB_PATH = "buyerhunter.db"


def get_unenriched_companies(db_path: str, limit: int, min_score: int = 0) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM companies
        WHERE website IS NOT NULL AND website != ''
        AND (enriched_at IS NULL OR enriched_at = '')
        AND lead_score <= ?
        ORDER BY lead_score DESC, id
        LIMIT ?""",
        (min_score, limit),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_company_by_id(db_path: str, company_id: int) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_company_enrichment(db_path: str, company_id: int, data: dict):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """UPDATE companies SET
        about_us = COALESCE(?, about_us),
        brands = COALESCE(?, brands),
        industries_served = COALESCE(?, industries_served),
        company_description = COALESCE(?, company_description),
        contact_page = COALESCE(?, contact_page),
        careers_page = COALESCE(?, careers_page),
        procurement_info = COALESCE(?, procurement_info),
        estimated_size = COALESCE(?, estimated_size),
        potential_oil_usage = COALESCE(?, potential_oil_usage),
        estimated_annual_consumption = COALESCE(?, estimated_annual_consumption),
        lead_score = COALESCE(?, lead_score),
        industry = COALESCE(?, industry),
        ai_reason = COALESCE(?, ai_reason),
        ai_confidence = COALESCE(?, ai_confidence),
        ai_consumption = COALESCE(?, ai_consumption),
        ai_frequency = COALESCE(?, ai_frequency),
        enriched_at = CURRENT_TIMESTAMP,
        updated_at = CURRENT_TIMESTAMP
        WHERE id = ?""",
        (
            data.get("about_us"),
            data.get("brands"),
            data.get("industries_served"),
            data.get("company_description"),
            data.get("contact_page"),
            data.get("careers_page"),
            data.get("procurement_info"),
            data.get("estimated_size"),
            data.get("potential_oil_usage"),
            data.get("estimated_annual_consumption"),
            data.get("lead_score"),
            data.get("industry"),
            data.get("ai_reason"),
            data.get("ai_confidence"),
            data.get("ai_consumption"),
            data.get("ai_frequency"),
            company_id,
        ),
    )
    conn.commit()
    conn.close()


def print_enrichment_report(results: list[dict]):
    print("\n" + "=" * 70)
    print("LEAD ENRICHMENT REPORT")
    print("=" * 70)

    if not results:
        print("No companies enriched.")
        print("=" * 70)
        return

    enriched = [r for r in results if r.get("status") == "completed"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    errors = [r for r in results if r.get("status") == "error"]

    print(f"\nTotal processed: {len(results)}")
    print(f"  Enriched:  {len(enriched)}")
    print(f"  Skipped:   {len(skipped)}")
    print(f"  Errors:    {len(errors)}")

    if enriched:
        print(f"\n{'ID':<6} {'Score':<7} {'Size':<12} {'Oil Usage':<12} {'Company':<35}")
        print("-" * 80)
        for r in enriched[:15]:
            name = r.get("company_name", "Unknown")[:33]
            print(
                f"{r.get('company_id', '?'):<6} "
                f"{r.get('lead_score', 0):<7} "
                f"{r.get('estimated_size', '?'):<12} "
                f"{r.get('potential_oil_usage', '?'):<12} "
                f"{name}"
            )

    if errors:
        print(f"\nErrors:")
        for r in errors:
            print(f"  {r.get('company_name', '?')}: {r.get('error', 'Unknown')}")

    print("=" * 70)


async def run_enrichment(db_path: str, limit: int, min_score: int, company_id: int | None):
    from backend.services.enrichment import EnrichmentService

    service = EnrichmentService()

    try:
        if company_id:
            company = get_company_by_id(db_path, company_id)
            if not company:
                logger.error(f"Company {company_id} not found")
                return []
            companies = [company]
        else:
            companies = get_unenriched_companies(db_path, limit, min_score)

        if not companies:
            logger.info("No companies to enrich")
            return []

        logger.info(f"Enriching {len(companies)} companies...")

        results = []
        for i, company in enumerate(companies):
            try:
                logger.info(f"[{i+1}/{len(companies)}] Enriching: {company['company_name']} ({company.get('website', 'no url')})")

                # Run enrichment
                enrichment_result = await service.enrich_company(company["id"])
                enrichment_result["company_name"] = company["company_name"]
                results.append(enrichment_result)

                if enrichment_result.get("status") == "completed":
                    logger.info(f"  -> Score: {enrichment_result.get('lead_score', '?')}, Size: {enrichment_result.get('estimated_size', '?')}")

                # Rate limit
                await asyncio.sleep(2.0)

            except Exception as e:
                logger.error(f"Failed to enrich {company.get('company_name')}: {e}")
                results.append({
                    "status": "error",
                    "company_name": company.get("company_name"),
                    "error": str(e),
                })

        return results

    finally:
        await service.close()


def main():
    parser = argparse.ArgumentParser(description="BuyerHunter AI Lead Enrichment")
    parser.add_argument("--db", default=DB_PATH, help="SQLite database path")
    parser.add_argument("--limit", type=int, default=50, help="Max companies to enrich")
    parser.add_argument("--min-score", type=int, default=0, help="Only enrich companies with score <= this")
    parser.add_argument("--company-id", type=int, help="Enrich a specific company by ID")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    results = asyncio.run(run_enrichment(str(db_path), args.limit, args.min_score, args.company_id))
    print_enrichment_report(results)


if __name__ == "__main__":
    main()
