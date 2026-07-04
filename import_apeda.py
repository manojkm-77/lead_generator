"""
BuyerHunter AI — APEDA Exporter Directory Importer

Scrapes the live APEDA Exporter Directory API to find food industry
companies registered with APEDA. These companies often import crude
palm oil and export finished food products.

API base: https://traceability.apeda.gov.in/apedamobile/api/apedaWebsite/

Usage:
    python import_apeda.py                          # scrape all food exporters
    python import_apeda.py --state AP               # filter by state code
    python import_apeda.py --from-file data.csv     # import from local file
"""

import csv
import json
import logging
import re
import sqlite3
import argparse
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("apeda")

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

API_BASE = "https://traceability.apeda.gov.in/apedamobile/api/apedaWebsite"
ENDPOINTS = {
    "states": f"{API_BASE}/ExporterDirectory_state",
    "products": f"{API_BASE}/ExporterDirectory_product",
    "search": f"{API_BASE}/ExporterDirectory_AllResult",
}

# Product IDs relevant to palm oil / edible oil industry
EDIBLE_OIL_PRODUCT_IDS = [
    "0501",  # HPS Groundnuts
    "0502",  # Guar Gum
    "0503",  # Jaggery & Confectionery
    "0504",  # Cocoa Products
    "0505",  # Cereal Preparations
    "0506",  # Alcoholic & Non-Alcoholic Beverages
    "0507",  # Miscellaneous Preparations
    "0801",  # De-Oiled Rice Bran
    "0701",  # Cashew Kernels
]

# Keywords indicating palm oil / edible oil related companies
OIL_KEYWORDS = [
    "oil", "fat", "vanaspati", "shortening", "margarine",
    "refin", "palm", "soybean", "sunflower", "mustard",
    "groundnut", "edible", "cooking", "food", "bakery",
    "confection", "chocolate", "cocoa", "dairy",
]

# Indian cities with significant edible oil processing
OIL_CITIES = {
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "mumbai": ("Mumbai", "Maharashtra"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "kolkata": ("Kolkata", "West Bengal"),
    "erode": ("Erode", "Tamil Nadu"),
    "indore": ("Indore", "Madhya Pradesh"),
    "rajkot": ("Rajkot", "Gujarat"),
    "navsari": ("Navsari", "Gujarat"),
    "surat": ("Surat", "Gujarat"),
    "jodhpur": ("Jodhpur", "Rajasthan"),
    "delhi": ("Delhi", "Delhi"),
    "new delhi": ("New Delhi", "Delhi"),
    "hyderabad": ("Hyderabad", "Telangana"),
    "bangalore": ("Bangalore", "Karnataka"),
    "bengaluru": ("Bengaluru", "Karnataka"),
    "ludhiana": ("Ludhiana", "Punjab"),
    "vadodara": ("Vadodara", "Gujarat"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "noida": ("Noida", "Uttar Pradesh"),
    "gurgaon": ("Gurgaon", "Haryana"),
    "jamnagar": ("Jamnagar", "Gujarat"),
    "tuticorin": ("Tuticorin", "Tamil Nadu"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "cochin": ("Cochin", "Kerala"),
    "kochi": ("Cochin", "Kerala"),
    "pune": ("Pune", "Maharashtra"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "bhopal": ("Bhopal", "Madhya Pradesh"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "patna": ("Patna", "Bihar"),
    "guwahati": ("Guwahati", "Assam"),
}


def guess_city_state(address: str, city_hint: str = "", state_hint: str = "") -> tuple:
    """Extract city and state from address using hints and keyword matching."""
    city = city_hint.strip() if city_hint else None
    state = state_hint.strip() if state_hint else None

    if not city and address:
        addr_lower = address.lower()
        for key, (c, s) in OIL_CITIES.items():
            if key in addr_lower:
                city = c
                if not state:
                    state = s
                break

    return city, state


def is_food_industry_company(name: str) -> bool:
    """Check if company name suggests food/edible oil industry."""
    name_lower = name.lower()
    for kw in OIL_KEYWORDS:
        if kw in name_lower:
            return True
    return False


class APEDADirectoryImporter:
    """Scrape APEDA Exporter Directory for food industry companies."""

    def __init__(self, db_path: str = "buyerhunter.db"):
        self.db_path = db_path
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Content-Type": "application/json",
            },
        )
        self.stats = {
            "states_fetched": 0,
            "products_fetched": 0,
            "companies_fetched": 0,
            "food_companies": 0,
            "new_saved": 0,
            "duplicates_skipped": 0,
        }

    def ensure_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website TEXT, phone TEXT, whatsapp TEXT, email TEXT,
                address TEXT, city TEXT, state TEXT,
                country TEXT DEFAULT 'India', gst_number TEXT,
                industry TEXT, products TEXT,
                lead_score INTEGER DEFAULT 0,
                source TEXT, crawl_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spider_name TEXT, start_time TEXT, end_time TEXT,
                pages_crawled INTEGER DEFAULT 0,
                companies_found INTEGER DEFAULT 0,
                duplicates_removed INTEGER DEFAULT 0,
                errors TEXT, status TEXT DEFAULT 'running'
            )
        """)
        try:
            conn.execute("ALTER TABLE companies ADD COLUMN exporter_type TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE companies ADD COLUMN apeda_state_code TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        conn.close()

    def fetch_states(self) -> list:
        r = self.client.post(ENDPOINTS["states"], json={"qType": "7"})
        r.raise_for_status()
        data = r.json()
        states = data.get("table", [])
        self.stats["states_fetched"] = len(states)
        return states

    def fetch_products(self) -> list:
        r = self.client.post(ENDPOINTS["products"], json={"qType": "1"})
        r.raise_for_status()
        data = r.json()
        products = data.get("table", [])
        self.stats["products_fetched"] = len(products)
        return products

    def search_exporters(self, state_code: str = "", product_id: str = "0000",
                         exporter_type: str = "ALL", name: str = "") -> list:
        payload = {
            "qType": "13",
            "expName": name,
            "expState": state_code,
            "expType": exporter_type,
            "expProduct": product_id,
        }
        r = self.client.post(ENDPOINTS["search"], json=payload)
        r.raise_for_status()
        data = r.json()
        return data.get("table", [])

    def run(self, state_code: str = "", product_ids: list = None,
            from_file: str = None):
        logger.info("=" * 60)
        logger.info("BUYERHUNTER AI — APEDA Exporter Directory Importer")
        logger.info("=" * 60)

        self.ensure_db()

        if from_file:
            records = self._load_csv(from_file)
        else:
            records = self._scrape_directory(state_code, product_ids)

        self.stats["companies_fetched"] = len(records)
        logger.info(f"Total companies fetched: {len(records)}")

        food_records = [r for r in records if is_food_industry_company(
            r.get("exporter_name", "")
        )]
        self.stats["food_companies"] = len(food_records)
        logger.info(f"Food/edible oil related: {len(food_records)}")

        if not food_records:
            food_records = records

        self._save_companies(food_records)

        logger.info("=" * 60)
        logger.info("APEDA IMPORT COMPLETE")
        logger.info(f"  Companies fetched: {self.stats['companies_fetched']}")
        logger.info(f"  Food industry:     {self.stats['food_companies']}")
        logger.info(f"  New saved:         {self.stats['new_saved']}")
        logger.info(f"  Duplicates:        {self.stats['duplicates_skipped']}")
        logger.info("=" * 60)

        self._log_crawl()

    def _scrape_directory(self, state_code: str, product_ids: list = None) -> list:
        all_records = []

        if product_ids:
            for pid in product_ids:
                logger.info(f"Searching product ID: {pid}")
                try:
                    rows = self.search_exporters(
                        state_code=state_code, product_id=pid
                    )
                    all_records.extend(rows)
                    logger.info(f"  Found {len(rows)} exporters")
                except Exception as e:
                    logger.warning(f"  Failed: {e}")
        else:
            logger.info("Searching all products (no filter)...")
            try:
                rows = self.search_exporters(state_code=state_code)
                all_records.extend(rows)
                logger.info(f"  Found {len(rows)} exporters")
            except Exception as e:
                logger.warning(f"  Search failed: {e}")

            if state_code:
                logger.info("Also searching food-specific product categories...")
                for pid in EDIBLE_OIL_PRODUCT_IDS:
                    try:
                        rows = self.search_exporters(
                            state_code=state_code, product_id=pid
                        )
                        all_records.extend(rows)
                    except Exception:
                        pass

        # Deduplicate by exporter name
        seen = set()
        unique = []
        for rec in all_records:
            name = (rec.get("exporter_name") or "").strip().lower()
            if name and name not in seen:
                seen.add(name)
                unique.append(rec)

        return unique

    def _load_csv(self, filepath: str) -> list:
        path = Path(filepath)
        if not path.exists():
            logger.error(f"File not found: {filepath}")
            return []

        records = []
        for enc in ["utf-8", "latin-1", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rec = {k.lower().strip(): v.strip() for k, v in row.items() if k and v}
                        if rec:
                            records.append(rec)
                break
            except UnicodeDecodeError:
                continue
        return records

    def _save_companies(self, records: list):
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()

        for rec in records:
            name = (
                rec.get("exporter_name") or rec.get("company_name") or ""
            ).strip()
            if not name or len(name) < 3:
                continue

            address = rec.get("address", "")
            city_hint = rec.get("city", "")
            state_hint = rec.get("state", "")
            city, state = guess_city_state(address, city_hint, state_hint)

            existing = conn.execute(
                "SELECT id FROM companies WHERE LOWER(company_name) = ?",
                (name.lower(),),
            ).fetchone()
            if existing:
                self.stats["duplicates_skipped"] += 1
                continue

            email = rec.get("email", "")
            exp_type = rec.get("expType", "") or rec.get("exporter_type", "")
            pin = rec.get("pin", "")
            full_address = f"{address}, {city_hint}" if address else city_hint
            if pin:
                full_address += f" - {pin}"

            try:
                conn.execute(
                    """INSERT INTO companies
                    (company_name, website, phone, whatsapp, email, address,
                     city, state, country, gst_number, industry, products,
                     lead_score, source, crawl_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        None, None, None,
                        email if email else None,
                        full_address if full_address else None,
                        city, state, "India", None,
                        "Edible Oil / Food Processing",
                        "APEDA Registered Exporter",
                        0, "apeda", now,
                    ),
                )
                self.stats["new_saved"] += 1
            except Exception as e:
                logger.warning(f"Insert failed for {name}: {e}")

        conn.commit()
        conn.close()

    def _log_crawl(self):
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO crawl_logs
            (spider_name, start_time, end_time, pages_crawled,
             companies_found, duplicates_removed, errors, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "apeda", now, now, 1,
                self.stats["new_saved"],
                self.stats["duplicates_skipped"],
                json.dumps([]), "completed",
            ),
        )
        conn.commit()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="APEDA Exporter Directory Importer")
    parser.add_argument("--state", default="", help="State code (e.g. GJ, MH, TN)")
    parser.add_argument("--products", nargs="+", default=None,
                        help="Product IDs to search (e.g. 0501 0502)")
    parser.add_argument("--from-file", help="Import from local CSV file")
    parser.add_argument("--db", default="buyerhunter.db", help="Database path")
    args = parser.parse_args()

    importer = APEDADirectoryImporter(db_path=args.db)
    importer.run(
        state_code=args.state,
        product_ids=args.products,
        from_file=args.from_file,
    )


if __name__ == "__main__":
    main()
