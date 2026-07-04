"""
BuyerHunter AI — IndiaMART Spider (Standalone)

Direct HTTP-based spider that doesn't depend on Twisted/Scrapy reactor.
Uses httpx for requests and BeautifulSoup for parsing.

Usage:
    python crawl_indiamart.py
    python crawl_indiamart.py --queries "palm oil dealer" --max-pages 2
"""

import re
import csv
import json
import sqlite3
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("indiamart")

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

SEARCH_URL = "https://www.indiamart.com/search.mp"

DEFAULT_QUERIES = [
    "palm oil buyer india",
    "edible oil distributor",
    "cooking oil wholesale",
]

INDUSTRY_MAP = {
    "bakery": "Bakery", "snack": "Bakery", "namkeen": "Bakery",
    "hotel": "Hotel", "restaurant": "Hotel",
    "wholesale": "Wholesaler", "wholesaler": "Wholesaler", "dealer": "Wholesaler",
    "distributor": "Distributor",
    "manufacturer": "Food Manufacturer", "factory": "Food Manufacturer",
    "retail": "Retail Chain", "supermarket": "Retail Chain",
    "import": "Importer", "export": "Exporter",
}


def clean(text):
    if not text:
        return None
    text = re.sub(r"\s+", " ", text.strip())
    return text if text else None


def parse_location(text):
    if not text:
        return None, None
    parts = [p.strip() for p in text.split(",")]
    city = parts[0] if parts else None
    state = parts[-1] if len(parts) > 1 else None
    if state and len(state) < 3:
        state = None
    return city, state


def guess_industry(query):
    q = query.lower()
    for keyword, industry in INDUSTRY_MAP.items():
        if keyword in q:
            return industry
    return "Food Processing Company"


def extract_cards(soup, query):
    """Extract company data from search result cards."""
    companies = []

    # Try multiple card selectors
    cards = (
        soup.select("div.card") or
        soup.select("div.lst-bx") or
        soup.select("div.srp-card") or
        soup.select("div.product-item") or
        soup.select("li.cntanr") or
        soup.select("div[class*='card']")
    )

    for card in cards:
        # Extract name
        name = None
        for sel in ["h2 a", "span.prf-ttl", "a.prf-ttl", "div.prf-ttl", "h3 a", "span.lntk"]:
            el = card.select_one(sel)
            if el:
                name = clean(el.get_text())
                break

        if not name or len(name) < 2:
            continue

        # Extract location
        location = None
        for sel in ["span.lv-val", "span.dsc-cnt", "div.loc", "span.city"]:
            el = card.select_one(sel)
            if el:
                location = clean(el.get_text())
                break

        city, state = parse_location(location)

        # Extract phone
        phone = None
        for sel in ["span.dsc-cnt", "a[href^='tel:']"]:
            el = card.select_one(sel)
            if el:
                raw = el.get("href", "") or el.get_text()
                digits = re.sub(r"[^\d]", "", raw.replace("tel:", ""))
                if len(digits) >= 10:
                    phone = digits
                    break

        # Extract products
        products = []
        for sel in ["span.srpd-prd", "div.prd-name", "span.prdname"]:
            els = card.select(sel)
            if els:
                products = [clean(e.get_text()) for e in els if clean(e.get_text())]
                break

        companies.append({
            "company_name": name,
            "website": None,
            "phone": phone,
            "whatsapp": phone,
            "email": None,
            "address": None,
            "city": city,
            "state": state,
            "country": "India",
            "gst_number": None,
            "industry": guess_industry(query),
            "products": json.dumps(products[:5]) if products else None,
            "lead_score": 0,
            "source": "indiamart",
            "crawl_date": datetime.now(timezone.utc).isoformat(),
        })

    return companies


def crawl_search(client, query, max_pages):
    """Crawl search results for a query."""
    all_companies = []

    for page in range(1, max_pages + 1):
        url = f"{SEARCH_URL}?{urlencode({'ss': query, 'page': page})}"
        logger.info(f"Fetching page {page}/{max_pages} for '{query}'")

        try:
            resp = client.get(url, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                companies = extract_cards(soup, query)
                all_companies.extend(companies)
                logger.info(f"  Found {len(companies)} companies on page {page}")
            elif resp.status_code == 429:
                logger.warning(f"  Rate limited on page {page}, waiting 10s...")
                import time; time.sleep(10)
            else:
                logger.warning(f"  HTTP {resp.status_code} on page {page}")
        except Exception as e:
            logger.error(f"  Error on page {page}: {e}")

        # Rate limit between pages
        if page < max_pages:
            import time; time.sleep(4)

    return all_companies


def save_to_sqlite(companies, db_path="buyerhunter.db"):
    """Save companies to SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            website TEXT, phone TEXT, whatsapp TEXT, email TEXT,
            address TEXT, city TEXT, state TEXT, country TEXT DEFAULT 'India',
            gst_number TEXT, industry TEXT, products TEXT,
            lead_score INTEGER DEFAULT 0, source TEXT, crawl_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    saved = 0
    duplicates = 0

    for company in companies:
        name = (company.get("company_name") or "").strip().lower()
        phone = company.get("phone") or ""

        # Check duplicate
        existing = conn.execute(
            "SELECT id FROM companies WHERE LOWER(company_name) = ? AND (phone = ? OR phone IS NULL OR phone = '')",
            (name, phone)
        ).fetchone()

        if existing:
            duplicates += 1
            continue

        conn.execute(
            """INSERT INTO companies
            (company_name, website, phone, whatsapp, email, address,
             city, state, country, gst_number, industry, products,
             lead_score, source, crawl_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                company.get("company_name"),
                company.get("website"),
                company.get("phone"),
                company.get("whatsapp"),
                company.get("email"),
                company.get("address"),
                company.get("city"),
                company.get("state"),
                company.get("country", "India"),
                company.get("gst_number"),
                company.get("industry"),
                company.get("products"),
                company.get("lead_score", 0),
                company.get("source"),
                company.get("crawl_date"),
            )
        )
        saved += 1

    conn.commit()
    conn.close()
    return saved, duplicates


def export_csv(companies, filename):
    """Export companies to CSV."""
    if not companies:
        return

    fieldnames = [
        "company_name", "website", "phone", "whatsapp", "email",
        "address", "city", "state", "country", "gst_number",
        "industry", "products", "lead_score", "source", "crawl_date",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for company in companies:
            row = {k: company.get(k, "") for k in fieldnames}
            writer.writerow(row)


def print_summary(total, saved, duplicates, emails, phones, csv_path):
    """Print crawl summary."""
    print("\n" + "=" * 60)
    print("BUYERHUNTER AI — IndiaMART Crawl Results")
    print("=" * 60)
    print(f"Total extracted:    {total}")
    print(f"Saved to DB:        {saved}")
    print(f"Duplicates skipped: {duplicates}")
    print(f"Emails found:       {emails}")
    print(f"Phones found:       {phones}")
    print(f"CSV exported:       {csv_path}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="IndiaMART Spider")
    parser.add_argument("--queries", nargs="+", default=DEFAULT_QUERIES, help="Search queries")
    parser.add_argument("--max-pages", type=int, default=2, help="Max pages per query")
    parser.add_argument("--db", default="buyerhunter.db", help="SQLite database path")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = EXPORT_DIR / f"indiamart_{timestamp}.csv"

    logger.info(f"Starting IndiaMART crawl")
    logger.info(f"Queries: {args.queries}")
    logger.info(f"Max pages: {args.max_pages}")

    all_companies = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, verify=False) as client:
        for query in args.queries:
            companies = crawl_search(client, query, args.max_pages)
            all_companies.extend(companies)
            logger.info(f"Total for '{query}': {len(companies)}")

    logger.info(f"\nTotal companies extracted: {len(all_companies)}")

    # Save to SQLite
    saved, duplicates = save_to_sqlite(all_companies, args.db)
    logger.info(f"Saved: {saved}, Duplicates: {duplicates}")

    # Export CSV
    export_csv(all_companies, csv_path)
    logger.info(f"CSV exported: {csv_path}")

    # Count contacts
    emails = sum(1 for c in all_companies if c.get("email"))
    phones = sum(1 for c in all_companies if c.get("phone"))

    # Print summary
    print_summary(len(all_companies), saved, duplicates, emails, phones, csv_path)


if __name__ == "__main__":
    main()
