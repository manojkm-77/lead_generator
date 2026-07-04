"""
BuyerHunter AI — Edible Oil Companies Spider

Crawls a curated list of real edible oil company websites.
Extracts publicly available business information.

This spider works reliably because it targets known company websites
rather than depending on search result pages.

Usage:
    python crawl_companies.py
    python crawl_companies.py --max-companies 10
"""

import re
import csv
import json
import sqlite3
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("crawler")

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Real edible oil companies in India with their websites
COMPANIES = [
    {"name": "Adani Wilmar", "website": "https://www.adaniwilmar.com", "industry": "Food Manufacturer", "city": "Ahmedabad", "state": "Gujarat"},
    {"name": "Marico Limited", "website": "https://www.marico.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Ruchi Soya Industries", "website": "https://www.ruchisooya.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Bunge India", "website": "https://www.bunge.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Cargill India", "website": "https://www.cargill.com", "industry": "Food Manufacturer", "city": "Gurgaon", "state": "Haryana"},
    {"name": "Emami Agrotech", "website": "https://www.emamiagrotech.com", "industry": "Food Manufacturer", "city": "Kolkata", "state": "West Bengal"},
    {"name": "Fortune Foods", "website": "https://www.fortunefoods.com", "industry": "Food Manufacturer", "city": "Ahmedabad", "state": "Gujarat"},
    {"name": "KPL Sugars & Refineries", "website": "https://www.kplsugars.com", "industry": "Food Manufacturer", "city": "Chennai", "state": "Tamil Nadu"},
    {"name": "Agro Tech Foods", "website": "https://www.agrotechfoods.com", "industry": "Food Manufacturer", "city": "Delhi", "state": "Delhi"},
    {"name": "Allana Group", "website": "https://www.allanagroup.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Parle Products", "website": "https://www.parleproducts.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Britannia Industries", "website": "https://www.britannia.co.in", "industry": "Food Manufacturer", "city": "Bangalore", "state": "Karnataka"},
    {"name": "Haldiram's", "website": "https://www.haldirams.com", "industry": "Food Manufacturer", "city": "Delhi", "state": "Delhi"},
    {"name": "Balaji Wafers", "website": "https://www.balajiwafers.com", "industry": "Food Manufacturer", "city": "Ahmedabad", "state": "Gujarat"},
    {"name": "Lays India", "website": "https://www.lays.com", "industry": "Food Manufacturer", "city": "Delhi", "state": "Delhi"},
    {"name": "ITC Foods", "website": "https://www.itcportal.com", "industry": "Food Manufacturer", "city": "Kolkata", "state": "West Bengal"},
    {"name": "Patanjali Ayurved", "website": "https://www.patanjaliayurved.net", "industry": "Food Manufacturer", "city": "Haridwar", "state": "Uttarakhand"},
    {"name": "Dabur India", "website": "https://www.dabur.com", "industry": "Food Manufacturer", "city": "Delhi", "state": "Delhi"},
    {"name": "Godrej Consumer Products", "website": "https://www.godrejcp.com", "industry": "Food Manufacturer", "city": "Mumbai", "state": "Maharashtra"},
    {"name": "Nestle India", "website": "https://www.nestle.in", "industry": "Food Manufacturer", "city": "Gurgaon", "state": "Haryana"},
]


def clean(text):
    if not text:
        return None
    text = re.sub(r"\s+", " ", text.strip())
    return text if text else None


def extract_company_info(soup, url):
    """Extract company information from their website."""
    info = {
        "website": url,
        "phone": None,
        "email": None,
        "address": None,
        "city": None,
        "state": None,
        "products": None,
        "about_us": None,
    }

    # Extract emails
    emails = set()
    for a in soup.select("a[href^='mailto:']"):
        email = a["href"].replace("mailto:", "").split("?")[0].strip()
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            emails.add(email.lower())
    if emails:
        info["email"] = list(emails)[0]

    # Extract phones
    phones = set()
    for a in soup.select("a[href^='tel:']"):
        phone = a["href"].replace("tel:", "").strip()
        digits = re.sub(r"[^\d]", "", phone)
        if len(digits) >= 10:
            phones.add(digits)
    if phones:
        info["phone"] = list(phones)[0]

    # Extract address
    for sel in ["[itemprop='address']", ".address", "footer .location", "footer address"]:
        el = soup.select_one(sel)
        if el:
            info["address"] = clean(el.get_text(separator=", "))
            break

    # Extract meta description as about
    meta = soup.select_one("meta[name='description']")
    if meta and meta.get("content"):
        info["about_us"] = clean(meta["content"])

    # Extract products from page
    products = []
    for sel in ["h2", "h3", "li"]:
        for el in soup.select(sel):
            text = clean(el.get_text())
            if text and len(text) < 60 and any(kw in text.lower() for kw in ["oil", "food", "snack", "bakery", "cooking"]):
                products.append(text)
    if products:
        info["products"] = json.dumps(products[:5])

    return info


def crawl_company(client, company_data):
    """Crawl a single company website."""
    url = company_data["website"]
    name = company_data["name"]

    logger.info(f"Crawling: {name} ({url})")

    try:
        resp = client.get(url, timeout=20)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            info = extract_company_info(soup, url)

            return {
                "company_name": name,
                "website": url,
                "phone": info.get("phone"),
                "whatsapp": info.get("phone"),
                "email": info.get("email"),
                "address": info.get("address"),
                "city": company_data.get("city"),
                "state": company_data.get("state"),
                "country": "India",
                "gst_number": None,
                "industry": company_data.get("industry"),
                "products": info.get("products"),
                "lead_score": 0,
                "source": "companywebsite",
                "crawl_date": datetime.now(timezone.utc).isoformat(),
            }
        else:
            logger.warning(f"  HTTP {resp.status_code} for {url}")
            return None
    except Exception as e:
        logger.error(f"  Error crawling {url}: {e}")
        return None


def save_to_sqlite(companies, db_path="buyerhunter.db"):
    """Save companies to SQLite."""
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
        if not company:
            continue

        name = (company.get("company_name") or "").strip().lower()

        existing = conn.execute(
            "SELECT id FROM companies WHERE LOWER(company_name) = ?",
            (name,)
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
    """Export to CSV."""
    fieldnames = [
        "company_name", "website", "phone", "email", "address",
        "city", "state", "country", "industry", "products",
        "lead_score", "source", "crawl_date",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for company in companies:
            if company:
                row = {k: company.get(k, "") for k in fieldnames}
                writer.writerow(row)


def main():
    parser = argparse.ArgumentParser(description="Edible Oil Companies Spider")
    parser.add_argument("--max-companies", type=int, default=20, help="Max companies to crawl")
    parser.add_argument("--db", default="buyerhunter.db", help="Database path")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = EXPORT_DIR / f"companies_{timestamp}.csv"

    logger.info("=" * 60)
    logger.info("BUYERHUNTER AI — Edible Oil Companies Spider")
    logger.info("=" * 60)
    logger.info(f"Companies to crawl: {min(args.max_companies, len(COMPANIES))}")

    companies_to_crawl = COMPANIES[:args.max_companies]
    results = []

    with httpx.Client(headers=HEADERS, follow_redirects=True, verify=False) as client:
        for company in companies_to_crawl:
            result = crawl_company(client, company)
            if result:
                results.append(result)
                logger.info(f"  OK: {result['company_name']} - phone={result['phone']}, email={result['email']}")
            else:
                logger.info(f"  FAILED: {company['name']}")

    logger.info(f"\nCrawled: {len(results)}/{len(companies_to_crawl)} companies")

    # Save to SQLite
    saved, duplicates = save_to_sqlite(results, args.db)
    logger.info(f"Saved: {saved}, Duplicates: {duplicates}")

    # Export CSV
    export_csv(results, csv_path)

    # Summary
    emails = sum(1 for r in results if r.get("email"))
    phones = sum(1 for r in results if r.get("phone"))

    print("\n" + "=" * 60)
    print("BUYERHUNTER AI — Crawl Results")
    print("=" * 60)
    print(f"Companies crawled:   {len(results)}/{len(companies_to_crawl)}")
    print(f"Saved to DB:         {saved}")
    print(f"Duplicates skipped:  {duplicates}")
    print(f"Emails found:        {emails}")
    print(f"Phones found:        {phones}")
    print(f"CSV exported:        {csv_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
