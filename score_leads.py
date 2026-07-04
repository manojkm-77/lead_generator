"""
BuyerHunter AI — Lead Scoring Script

Scores all unscored companies in the database using Gemini AI.
Falls back to rule-based scoring when API is unavailable.

Usage:
    python score_leads.py                    # Score all unscored companies
    python score_leads.py --rescore          # Re-score all companies
    python score_leads.py --limit 50         # Score up to 50 companies
    python score_leads.py --company-id 123   # Score a specific company
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
logger = logging.getLogger("buyerhunter.scorer")

DB_PATH = "buyerhunter.db"


def get_unscored_companies(db_path: str, limit: int, rescore: bool = False) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if rescore:
        rows = conn.execute(
            "SELECT * FROM companies ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM companies WHERE lead_score = 0 OR lead_score IS NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

    companies = [dict(row) for row in rows]
    conn.close()
    return companies


def get_company_by_id(db_path: str, company_id: int) -> dict | None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_company_score(db_path: str, company_id: int, classification: dict):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """UPDATE companies SET
        lead_score = ?,
        industry = COALESCE(?, industry),
        ai_reason = ?,
        ai_confidence = ?,
        ai_consumption = ?,
        ai_frequency = ?,
        updated_at = CURRENT_TIMESTAMP
        WHERE id = ?""",
        (
            classification["lead_score"],
            classification.get("category"),
            classification.get("reason", ""),
            classification.get("confidence", 0),
            classification.get("consumption_estimate", "Unknown"),
            classification.get("buying_frequency", "Unknown"),
            company_id,
        ),
    )
    conn.commit()
    conn.close()


def print_score_report(results: list[dict]):
    print("\n" + "=" * 70)
    print("LEAD SCORING REPORT")
    print("=" * 70)

    if not results:
        print("No companies scored.")
        print("=" * 70)
        return

    scored = [r for r in results if r.get("classification")]
    high = [r for r in scored if r["classification"]["lead_score"] >= 70]
    medium = [r for r in scored if 40 <= r["classification"]["lead_score"] < 70]
    low = [r for r in scored if r["classification"]["lead_score"] < 40]

    print(f"\nTotal scored: {len(scored)}")
    print(f"  High quality (70+):  {len(high)}")
    print(f"  Medium (40-69):      {len(medium)}")
    print(f"  Low (0-39):          {len(low)}")

    print(f"\n{'ID':<6} {'Score':<7} {'Conf':<6} {'Category':<20} {'Company':<35}")
    print("-" * 80)
    for r in scored[:20]:
        c = r["classification"]
        name = r.get("company_name", "Unknown")[:33]
        print(
            f"{r['id']:<6} {c['lead_score']:<7} {c['confidence']:<6} "
            f"{c['category']:<20} {name}"
        )

    if len(scored) > 20:
        print(f"  ... and {len(scored) - 20} more")

    # Category distribution
    categories = {}
    for r in scored:
        cat = r["classification"]["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nCategory Distribution:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print("=" * 70)


async def run_scoring(db_path: str, limit: int, rescore: bool, company_id: int | None):
    from backend.services.ai_qualifier import AIQualifier

    qualifier = AIQualifier()

    if company_id:
        company = get_company_by_id(db_path, company_id)
        if not company:
            logger.error(f"Company {company_id} not found")
            return []
        companies = [company]
    else:
        companies = get_unscored_companies(db_path, limit, rescore)

    if not companies:
        logger.info("No companies to score")
        return []

    logger.info(f"Scoring {len(companies)} companies...")

    results = []
    for i, company in enumerate(companies):
        try:
            classification = await qualifier.classify(company)
            update_company_score(db_path, company["id"], classification)
            company["classification"] = classification
            results.append(company)

            score = classification["lead_score"]
            category = classification["category"]
            logger.info(
                f"[{i+1}/{len(companies)}] {company['company_name']}: "
                f"{category} (score={score})"
            )

            if qualifier.api_key:
                await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Failed to score {company.get('company_name')}: {e}")
            company["classification"] = qualifier._classify_with_rules(company)
            update_company_score(db_path, company["id"], company["classification"])
            results.append(company)

    return results


def main():
    parser = argparse.ArgumentParser(description="BuyerHunter AI Lead Scoring")
    parser.add_argument("--db", default=DB_PATH, help="SQLite database path")
    parser.add_argument("--limit", type=int, default=100, help="Max companies to score")
    parser.add_argument("--rescore", action="store_true", help="Re-score all companies")
    parser.add_argument("--company-id", type=int, help="Score a specific company by ID")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    results = asyncio.run(run_scoring(str(db_path), args.limit, args.rescore, args.company_id))
    print_score_report(results)


if __name__ == "__main__":
    main()
