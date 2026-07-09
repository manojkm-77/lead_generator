"""
BuyerHunter — End-to-End Pipeline Runner

Runs the full discovery pipeline:
1. Query expansion
2. Multi-source crawling
3. Company saving with evidence
4. Deduplication & merging
5. Results summary
"""

import asyncio
import logging
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_pipeline(
    query: str,
    max_queries: int = 50,
    max_pages_per_spider: int = 2,
    sources: list[str] | None = None,
    max_concurrent: int = 3,
):
    """Run the full BuyerHunter pipeline."""
    from backend.core.database import get_engine, get_session_factory, init_v2_db
    from backend.services.query_expander import QueryExpander
    from backend.services.crawler_service import MultiSourceCrawler, close_global_browser
    from backend.services.pipeline_service import (
        save_company_with_evidence,
        save_contact_with_evidence,
        run_dedup_pipeline,
        EvidenceCategory,
    )
    from backend.core.models.contact import ContactChannel, ContactPurpose
    from sqlalchemy import select, func
    from backend.core.models.company import Company

    start_time = time.time()

    # Initialize DB
    logger.info("Initializing database...")
    await init_v2_db()

    session_factory = get_session_factory()

    # Step 1: Expand queries
    logger.info(f"Step 1: Expanding query '{query}' (max={max_queries})...")
    expander = QueryExpander()
    variations = expander.expand(query, max_queries=max_queries)

    if sources:
        variations = [v for v in variations if v["source"] in sources]

    by_source = {}
    for v in variations:
        by_source[v["source"]] = by_source.get(v["source"], 0) + 1

    logger.info(f"Generated {len(variations)} queries across {len(by_source)} sources:")
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        logger.info(f"  {src}: {count} queries")

    if not variations:
        logger.error("No queries generated. Exiting.")
        return

    # Step 2: Crawl and save
    logger.info(f"Step 2: Crawling {len(variations)} queries (concurrent={max_concurrent})...")
    crawler = MultiSourceCrawler(timeout=30, max_pages=max_pages_per_spider)

    total_stats = {
        "companies_found": 0,
        "companies_new": 0,
        "emails_found": 0,
        "phones_found": 0,
        "websites_found": 0,
        "contacts_added": 0,
        "errors": 0,
        "queries_completed": 0,
    }

    sem = asyncio.Semaphore(max_concurrent)

    async def crawl_one(idx: int, v: dict) -> dict:
        async with sem:
            source = v["source"]
            query_str = v["query"]
            location = v.get("location", "")
            city = location if location else "Mumbai"

            # Map state names to cities
            from backend.services.query_expander import INDIAN_STATES_CITIES
            state_name = location
            city_name = city
            if location in INDIAN_STATES_CITIES:
                state_name = location
                city_name = INDIAN_STATES_CITIES[location][0] if INDIAN_STATES_CITIES[location] else "Mumbai"
            elif location:
                # It's a city name, find the state
                for st, cities in INDIAN_STATES_CITIES.items():
                    if location in cities:
                        state_name = st
                        city_name = location
                        break

            try:
                result = await crawler.crawl_job(
                    query_string=query_str,
                    source=source,
                    target_city=city_name,
                    target_state=state_name,
                )
            except Exception as e:
                logger.warning(f"[{idx+1}] Failed {source}/{query_str}: {e}")
                return {"errors": 1}

            stats = {"errors": 0, "companies": 0, "new": 0}
            async with session_factory() as db:
                for ec in result.companies:
                    stats["companies"] += 1
                    company = await save_company_with_evidence(
                        db,
                        {
                            "company_name": ec.company_name,
                            "website": ec.website,
                            "city": ec.city or city_name,
                            "state": ec.state or state_name,
                            "address": ec.address or "",
                            "industry": ec.industry or "",
                            "confidence": min(90, ec.confidence or 50),
                            "buyer_score": min(90, ec.confidence or 50),
                        },
                        source=source,
                        source_url=ec.source_url or "",
                        scraper_name=f"crawler_{source}",
                    )
                    if company:
                        stats["new"] += 1
                        if ec.email:
                            await save_contact_with_evidence(
                                db, company.id, ContactChannel.EMAIL, ec.email,
                                source_url=ec.source_url or "", scraper_name=source,
                                purpose=ContactPurpose.GENERAL, confidence=60,
                            )
                        if ec.phone:
                            await save_contact_with_evidence(
                                db, company.id, ContactChannel.PHONE, ec.phone,
                                source_url=ec.source_url or "", scraper_name=source,
                                purpose=ContactPurpose.GENERAL, confidence=60,
                            )
                await db.commit()

            logger.info(f"[{idx+1}/{len(variations)}] {source} '{query_str}': {stats['companies']} found, {stats['new']} new")
            return stats

    # Run all crawls
    tasks = [crawl_one(i, v) for i, v in enumerate(variations)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, Exception):
            total_stats["errors"] += 1
            continue
        total_stats["companies_found"] += res.get("companies", 0)
        total_stats["companies_new"] += res.get("new", 0)
        total_stats["errors"] += res.get("errors", 0)
        total_stats["queries_completed"] += 1

    await crawler.close()

    # Step 3: Deduplication
    logger.info("Step 3: Running deduplication...")
    async with session_factory() as db:
        dedup_result = await run_dedup_pipeline(db)

    # Step 4: Get final stats
    logger.info("Step 4: Computing final stats...")
    async with session_factory() as db:
        total_companies = (await db.execute(select(func.count(Company.id)))).scalar() or 0
        total_contacts_q = await db.execute(
            select(func.count()).select_from(
                select(Company.id).subquery()
            )
        )

        from backend.core.models.contact import Contact
        total_contacts = (await db.execute(select(func.count(Contact.id)))).scalar() or 0
        total_emails = (await db.execute(
            select(func.count(Contact.id)).where(Contact.channel == "email")
        )).scalar() or 0
        total_phones = (await db.execute(
            select(func.count(Contact.id)).where(Contact.channel == "phone")
        )).scalar() or 0

    elapsed = time.time() - start_time

    # Summary
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Query: {query}")
    logger.info(f"Time: {elapsed:.1f}s")
    logger.info(f"Queries completed: {total_stats['queries_completed']}/{len(variations)}")
    logger.info(f"Companies found this run: {total_stats['companies_found']}")
    logger.info(f"New companies added: {total_stats['companies_new']}")
    logger.info(f"Duplicates merged: {dedup_result.get('merged', 0)}")
    logger.info(f"Duplicates removed: {dedup_result.get('removed', 0)}")
    logger.info(f"Errors: {total_stats['errors']}")
    logger.info("-" * 60)
    logger.info("DATABASE TOTALS:")
    logger.info(f"  Total companies: {total_companies}")
    logger.info(f"  Total contacts: {total_contacts}")
    logger.info(f"  Emails: {total_emails}")
    logger.info(f"  Phones: {total_phones}")
    logger.info("=" * 60)

    return {
        "run_time": elapsed,
        "queries": len(variations),
        "companies_new": total_stats["companies_new"],
        "total_companies": total_companies,
        "total_contacts": total_contacts,
        "dedup_merged": dedup_result.get("merged", 0),
        "dedup_removed": dedup_result.get("removed", 0),
    }


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "palm oil buyers India"
    max_q = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    max_p = int(sys.argv[3]) if len(sys.argv) > 3 else 2

    logger.info(f"Starting pipeline: query='{query}', max_queries={max_q}, max_pages={max_p}")

    result = asyncio.run(run_pipeline(
        query=query,
        max_queries=max_q,
        max_pages_per_spider=max_p,
    ))

    if result:
        logger.info(f"Pipeline finished successfully.")
