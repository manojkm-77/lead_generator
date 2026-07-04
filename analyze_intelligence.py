"""
BuyerHunter AI — Intelligence Analysis Script

Runs the full buyer intelligence pipeline on companies.

Usage:
    python analyze_intelligence.py                      # Analyze unprocessed companies
    python analyze_intelligence.py --limit 20           # Analyze up to 20
    python analyze_intelligence.py --company-id 123     # Analyze specific company
    python analyze_intelligence.py --stats              # Show statistics
"""

import argparse
import asyncio
import json
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("buyerhunter.intelligence")

DB_PATH = "buyerhunter.db"


def print_stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    analyzed = conn.execute("SELECT COUNT(*) FROM buyer_scores").fetchone()[0]
    contacts = conn.execute("SELECT COUNT(*) FROM procurement_contacts").fetchone()[0]
    products = conn.execute("SELECT COUNT(*) FROM product_detections").fetchone()[0]

    # Score distribution
    score_dist = conn.execute("""
        SELECT
            CASE
                WHEN buyer_score >= 76 THEN '76-100'
                WHEN buyer_score >= 51 THEN '51-75'
                WHEN buyer_score >= 26 THEN '26-50'
                ELSE '0-25'
            END as range,
            COUNT(*) as count
        FROM buyer_scores
        GROUP BY range
    """).fetchall()

    # Priority distribution
    priority_dist = conn.execute(
        "SELECT buyer_priority, COUNT(*) FROM buyer_scores GROUP BY buyer_priority"
    ).fetchall()

    # Top buyers
    top = conn.execute("""
        SELECT c.company_name, b.buyer_score, b.buyer_priority, b.lead_temperature
        FROM buyer_scores b
        JOIN companies c ON b.company_id = c.id
        ORDER BY b.buyer_score DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    print("\n" + "=" * 60)
    print("BUYER INTELLIGENCE — Statistics")
    print("=" * 60)
    print(f"Total companies:      {total}")
    print(f"Analyzed:             {analyzed}")
    print(f"Contacts discovered:  {contacts}")
    print(f"Products detected:    {products}")
    print(f"Analysis rate:        {round(analyzed/total*100, 1) if total else 0}%")

    if score_dist:
        print("\nScore Distribution:")
        for row in score_dist:
            print(f"  {row[0]}: {row[1]}")

    if priority_dist:
        print("\nPriority Distribution:")
        for row in priority_dist:
            print(f"  {row[0]}: {row[1]}")

    if top:
        print("\nTop 10 Buyers:")
        print(f"  {'Company':<35} {'Score':<7} {'Priority':<10} {'Temp'}")
        print("  " + "-" * 65)
        for row in top:
            print(f"  {row[0][:33]:<35} {row[1]:<7} {row[2]:<10} {row[3]}")

    print("=" * 60)


def print_intelligence_report(company_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    company = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    if not company:
        print(f"Company {company_id} not found")
        return

    score = conn.execute("SELECT * FROM buyer_scores WHERE company_id = ?", (company_id,)).fetchone()
    detection = conn.execute("SELECT * FROM product_detections WHERE company_id = ?", (company_id,)).fetchone()
    summary = conn.execute("SELECT * FROM buyer_summaries WHERE company_id = ?", (company_id,)).fetchone()
    contacts = conn.execute("SELECT * FROM procurement_contacts WHERE company_id = ?", (company_id,)).fetchall()

    conn.close()

    print("\n" + "=" * 70)
    print(f"BUYER INTELLIGENCE REPORT: {company['company_name']}")
    print("=" * 70)

    print(f"\nCompany: {company['company_name']}")
    print(f"Industry: {company['industry'] or 'Unknown'}")
    print(f"City: {company['city'] or 'Unknown'}")

    if score:
        print(f"\nBuyer Score: {score['buyer_score']}/100")
        print(f"Priority: {score['buyer_priority']}")
        print(f"Temperature: {score['lead_temperature']}")
        print(f"Monthly Consumption: {score['monthly_consumption']}")
        print(f"Annual Consumption: {score['annual_consumption']}")
        print(f"Buying Frequency: {score['buying_frequency']}")
        print(f"Company Size: {score['company_size']}")
        print(f"Procurement Maturity: {score['procurement_maturity']}")

    if detection:
        print("\nProduct Detection:")
        oils = ["palm_oil", "rbd_palm_olein", "sunflower_oil", "soybean_oil", "rice_bran_oil",
                "mustard_oil", "groundnut_oil", "coconut_oil", "vanaspati", "shortening", "bakery_fat"]
        for oil in oils:
            prob = detection[oil] or 0
            if prob >= 0.3:
                print(f"  {oil.replace('_', ' ').title()}: {round(prob*100)}%")

    if summary:
        print(f"\nAI Summary:")
        print(f"  {summary['company_summary']}")
        print(f"\nWhy Buyer:")
        print(f"  {summary['why_buyer']}")
        print(f"\nRecommended Pitch:")
        print(f"  {summary['recommended_pitch']}")

    if contacts:
        print(f"\nProcurement Contacts ({len(contacts)}):")
        for c in contacts:
            print(f"  {c['person_name']} - {c['designation'] or 'Unknown'} ({c['confidence_score']}%)")
            if c['email']:
                print(f"    Email: {c['email']}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="BuyerHunter AI Intelligence Analysis")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--company-id", type=int)
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    if args.company_id:
        print_intelligence_report(args.company_id)
        return

    from backend.services.intelligence import IntelligenceEngine
    engine = IntelligenceEngine()

    async def run():
        try:
            result = await engine.analyze_batch(args.limit)
            print(f"\nAnalysis complete: {result}")
            print_stats()
        finally:
            await engine.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
