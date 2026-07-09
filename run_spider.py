"""
BuyerHunter AI — Spider Runner

Runs Scrapy spiders, saves to SQLite, triggers AI scoring, exports CSV.

Usage:
    python run_spider.py --spider indiamart
    python run_spider.py --spider indiamart --queries "palm oil" --max-pages 2
    python run_spider.py --stats
"""

import argparse
import asyncio
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("buyerhunter.runner")

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)


def get_spider_settings(spider_name: str):
    """Build Scrapy settings for a spider."""
    csv_path = EXPORT_DIR / f"{spider_name}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    feed_path = EXPORT_DIR / f"{spider_name}_feed.json"

    return {
        "BOT_NAME": "buyerhunter",
        "SPIDER_MODULES": ["backend.spiders"],
        "NEWSPIDER_MODULE": "backend.spiders",
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_TIMEOUT": 30,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [429, 500, 502, 503, 504, 408],
        "LOG_LEVEL": "INFO",
        "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
        "TWISTED_REACTOR": "twisted.internet.asyncioreactor.AsyncioSelectorReactor",
        "SQLITE_DB_PATH": "buyerhunter.db",
        "CSV_OUTPUT_PATH": str(csv_path),
        "ITEM_PIPELINES": {
            "backend.spiders.pipelines.ValidationPipeline": 100,
            "backend.spiders.pipelines.CleanupPipeline": 200,
            "backend.spiders.db_pipelines.SQLitePipeline": 300,
            "backend.spiders.db_pipelines.CSVExportPipeline": 400,
        },
        "DOWNLOAD_DELAY": 4,
        "CONCURRENT_REQUESTS": 8,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 3,
        "RANDOMIZE_DOWNLOAD_DELAY": True,
        "HTTPCACHE_ENABLED": True,
        "HTTPCACHE_EXPIRATION_SECS": 3600,
        "HTTPCACHE_DIR": ".httpcache",
        "FEEDS": {
            str(feed_path): {"format": "json", "encoding": "utf-8", "overwrite": True},
        },
    }


def run_spider(spider_name: str, queries: list[str], max_pages: int):
    """Run a single spider."""
    from scrapy.crawler import CrawlerProcess

    settings = get_spider_settings(spider_name)
    process = CrawlerProcess(settings)

    spider_kwargs = {"max_pages": max_pages}
    if queries:
        spider_kwargs["queries"] = queries

    logger.info(f"Starting spider: {spider_name}")
    logger.info(f"Queries: {queries}")
    logger.info(f"Max pages: {max_pages}")

    process.crawl(spider_name, **spider_kwargs)
    process.start()

    csv_path = EXPORT_DIR / f"{spider_name}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    return csv_path


def trigger_ai_scoring():
    """Trigger AI scoring for unscored companies."""
    db_path = Path("buyerhunter.db")
    if not db_path.exists():
        return

    logger.info("Triggering AI scoring for unscored companies...")

    try:
        from backend.services.ai_qualifier import AIQualifier
        import sqlite3

        qualifier = AIQualifier()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        unscored = conn.execute(
            "SELECT * FROM companies WHERE lead_score = 0 OR lead_score IS NULL LIMIT 50"
        ).fetchall()

        if not unscored:
            logger.info("No unscored companies found")
            conn.close()
            return

        logger.info(f"Scoring {len(unscored)} companies...")

        async def score_batch():
            companies = [dict(row) for row in unscored]
            return await qualifier.classify_batch(companies)

        results = asyncio.run(score_batch())

        updated = 0
        for result in results:
            company_id = result.get("id")
            if company_id:
                conn.execute(
                    """UPDATE companies SET
                    lead_score = ?,
                    industry = COALESCE(?, industry),
                    ai_reason = ?,
                    ai_confidence = ?,
                    updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                    (
                        result.get("lead_score", 0),
                        result.get("industry"),
                        result.get("ai_reason", ""),
                        result.get("ai_confidence", 0),
                        company_id,
                    ),
                )
                updated += 1

        conn.commit()
        conn.close()
        logger.info(f"AI scoring complete: {updated} companies updated")

    except Exception as e:
        logger.warning(f"AI scoring failed (non-critical): {e}")


def print_summary():
    """Print crawl summary from database."""
    db_path = Path("buyerhunter.db")
    if not db_path.exists():
        logger.warning("No database file found")
        return

    conn = sqlite3.connect(str(db_path))

    try:
        total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        today = conn.execute(
            "SELECT COUNT(*) FROM companies WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]
        try:
            emails = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE email IS NOT NULL AND email != ''"
            ).fetchone()[0]
        except Exception:
            emails = 0
        try:
            phones = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE phone IS NOT NULL AND phone != ''"
            ).fetchone()[0]
        except Exception:
            phones = 0
        try:
            websites = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE website IS NOT NULL AND website != ''"
            ).fetchone()[0]
        except Exception:
            websites = 0
        try:
            high_quality = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE lead_score >= 70"
            ).fetchone()[0]
        except Exception:
            try:
                high_quality = conn.execute(
                    "SELECT COUNT(*) FROM companies WHERE buyer_score >= 70"
                ).fetchone()[0]
            except Exception:
                high_quality = 0
        try:
            sources = conn.execute(
                    "SELECT source, COUNT(*) FROM companies GROUP BY source"
                ).fetchall()
        except Exception:
            sources = []
        try:
            industries = conn.execute(
                "SELECT industry, COUNT(*) FROM companies WHERE industry IS NOT NULL GROUP BY industry ORDER BY COUNT(*) DESC LIMIT 5"
            ).fetchall()
        except Exception:
            industries = []

        print("\n" + "=" * 60)
        print("BUYERHUNTER AI — Crawl Summary")
        print("=" * 60)
        print(f"Total companies in DB:  {total}")
        print(f"New today:              {today}")
        print(f"Emails found:           {emails}")
        print(f"Phones found:           {phones}")
        print(f"Websites found:         {websites}")
        print(f"High quality (>=70):    {high_quality}")
        if sources:
            print("\nBy source:")
            for source, count in sources:
                print(f"  {source}: {count}")
        if industries:
            print("\nTop industries:")
            for ind, count in industries:
                print(f"  {ind}: {count}")
        print("=" * 60)
    finally:
        conn.close()


def list_spiders():
    """List available spiders."""
    spiders = {
        "indiamart": "IndiaMART B2B directory",
        "justdial": "JustDial local business directory",
        "tradeindia": "TradeIndia trade directory",
        "yellowpages": "Yellow Pages business directory",
        "exportersindia": "ExportersIndia export/import directory",
        "companywebsite": "Direct company website crawler",
        "apeda": "APEDA exporter directory (government)",
        "dgcis": "DGCIS import/export trade statistics (government)",
    }

    print("\nAvailable spiders:")
    print("-" * 50)
    for name, desc in spiders.items():
        print(f"  {name:20s} {desc}")
    print()


DEFAULT_QUERIES = [
    "palm oil buyer india",
    "edible oil distributor",
    "cooking oil wholesale",
]


def run_apeda_import(state="", from_file=None):
    """Run the APEDA exporter directory importer."""
    from import_apeda import APEDADirectoryImporter
    importer = APEDADirectoryImporter()
    importer.run(state_code=state, from_file=from_file)


def run_dgcis_import(hs_code="1511", year=None, all_years=False):
    """Run the DGCIS trade statistics importer."""
    from import_dgcis import DGCISImporter
    importer = DGCISImporter()
    importer.run(hs_code=hs_code, year=year, all_years=all_years)


def main():
    parser = argparse.ArgumentParser(description="BuyerHunter AI Spider Runner")
    parser.add_argument("--spider", help="Spider name to run")
    parser.add_argument("--queries", nargs="+", help="Search queries")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages per query")
    parser.add_argument("--list", action="store_true", help="List available spiders")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--no-score", action="store_true", help="Skip AI scoring after crawl")
    parser.add_argument("--year", type=int, default=None, help="Year for APEDA import")
    parser.add_argument("--months", type=int, default=3, help="Months for APEDA import")
    parser.add_argument("--from-file", type=str, default=None, help="Import from local file")
    args = parser.parse_args()

    if args.list:
        list_spiders()
        return

    if args.stats:
        print_summary()
        return

    if not args.spider:
        parser.print_help()
        return

    try:
        print(f"\n{'='*60}")
        print(f"BUYERHUNTER AI — Starting Crawl")
        print(f"Spider: {args.spider}")
        print(f"{'='*60}\n")

        if args.spider == "apeda":
            run_apeda_import(
                state=args.queries[0] if args.queries else "",
                from_file=args.from_file,
            )
        elif args.spider == "dgcis":
            run_dgcis_import(
                hs_code=args.queries[0] if args.queries else "1511",
                year=args.year,
                all_years=args.all_years,
            )
        else:
            queries = args.queries or DEFAULT_QUERIES
            print(f"Queries: {queries}")
            print(f"Max pages: {args.max_pages}")
            csv_path = run_spider(args.spider, queries, args.max_pages)

        # Trigger AI scoring
        if not args.no_score:
            trigger_ai_scoring()

        # Print summary
        print_summary()

        print(f"\n{'='*60}")
        print("CRAWL COMPLETE")
        print(f"{'='*60}\n")

    except KeyboardInterrupt:
        logger.info("Crawl interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
