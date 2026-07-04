"""
BuyerHunter AI — DGCIS TRADESTAT Import Data Scraper

Scrapes India's official import statistics from DGCIS (tradestat.commerce.gov.in)
for crude palm oil and related products. Provides market intelligence:
  - Which countries India imports palm oil from
  - Import values and quantities by year
  - Trade flow patterns

DGCIS provides AGGREGATE data (no company names), but this data is critical for:
  1. Understanding market size and growth
  2. Identifying source countries (Malaysia, Indonesia)
  3. Cross-referencing with company-level data from APEDA/IndiaMART

HS codes for palm oil:
  1511  — Crude palm oil
  151110 — Crude palm oil (not degummed)
  151190 — Other crude palm oil
  1513  — Palm kernel oil
  151311 — Crude palm kernel oil
  151319 — Other palm kernel oil

Usage:
    python import_dgcis.py                    # latest year, HS 1511
    python import_dgcis.py --hs 151110        # specific HS code
    python import_dgcis.py --year 2024        # specific year
    python import_dgcis.py --all-years        # all available years
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
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("dgcis")

EXPORT_DIR = Path("exports")
EXPORT_DIR.mkdir(exist_ok=True)

BASE_URL = "https://tradestat.commerce.gov.in"
IMPORT_URL = f"{BASE_URL}/eidb/commodity_wise_import"
CSRF_URL = f"{BASE_URL}/refresh-csrf"
HS_SEARCH_URL = f"{BASE_URL}/meidb/hscode"

PALM_OIL_HS_CODES = ["1511", "151110", "151190", "1513", "151311", "151319"]

AVAILABLE_YEARS = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018]


class DGCISImporter:
    """Scrape DGCIS TRADESTAT for palm oil import data."""

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
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        self.stats = {
            "queries_made": 0,
            "records_found": 0,
            "years_processed": 0,
        }

    def _get_csrf_token(self) -> str:
        """Fetch a fresh CSRF token from the site."""
        try:
            r = self.client.get(CSRF_URL)
            data = r.json()
            return data.get("token", "")
        except Exception:
            pass

        r = self.client.get(IMPORT_URL)
        soup = BeautifulSoup(r.text, "html.parser")
        token_input = soup.find("input", {"name": "_token"})
        if token_input:
            return token_input.get("value", "")
        meta = soup.find("meta", {"name": "csrf-token"})
        if meta:
            return meta.get("content", "")
        return ""

    def _search_hs_code(self, hs_code: str = "", description: str = "") -> list:
        """Search HS codes via the DGCIS API."""
        token = self._get_csrf_token()
        if not token:
            logger.warning("Could not get CSRF token for HS search")
            return []

        r = self.client.post(
            HS_SEARCH_URL,
            data={"_token": token, "hscode": hs_code, "description": description},
            headers={"X-CSRF-TOKEN": token},
        )
        try:
            return r.json()
        except Exception:
            return []

    def fetch_import_data(self, year: int, hs_code: str = "1511",
                          commodity_level: int = 4,
                          value_format: int = 2) -> list:
        """
        Fetch import data from DGCIS for a specific year and HS code.

        Args:
            year: Financial year (e.g. 2024 for 2024-2025)
            hs_code: HS code to search
            commodity_level: 2, 4, 6, or 8 digit level
            value_format: 1=₹ Crore, 2=US$ Million, 3=Quantity
        """
        token = self._get_csrf_token()
        if not token:
            logger.warning("Could not obtain CSRF token")
            return []

        form_data = {
            "_token": token,
            "Eidb_YearCwi": str(year),
            "commodityType": "specific",
            "Eidb_hscodeCwi": hs_code,
            "Eidb_ReportCwi": str(value_format),
        }

        logger.info(f"Fetching imports: year={year}, HS={hs_code}, format={value_format}")
        r = self.client.post(IMPORT_URL, data=form_data)
        self.stats["queries_made"] += 1

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table")
        if not table:
            logger.info(f"  No table found for year {year}")
            return []

        records = []
        rows = table.find_all("tr")
        if len(rows) < 2:
            return []

        headers = []
        for th in rows[0].find_all(["th", "td"]):
            headers.append(th.get_text(strip=True))

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            values = [c.get_text(strip=True) for c in cells]
            if len(values) >= 2:
                record = {"year": f"{year}-{year+1}"}
                for i, h in enumerate(headers):
                    if i < len(values):
                        record[h] = values[i]
                records.append(record)

        return records

    def run(self, hs_code: str = "1511", year: int = None,
            all_years: bool = False):
        logger.info("=" * 60)
        logger.info("BUYERHUNTER AI — DGCIS Import Data Scraper")
        logger.info("=" * 60)

        self.ensure_db()

        years = AVAILABLE_YEARS if all_years else [year or AVAILABLE_YEARS[0]]

        all_records = []
        for y in years:
            for fmt in [2, 3]:  # US$ and Quantity
                records = self.fetch_import_data(y, hs_code, value_format=fmt)
                all_records.extend(records)
                self.stats["records_found"] += len(records)
            self.stats["years_processed"] += 1

        if not all_records:
            logger.warning("No import data found")
            return

        self._save_trade_data(all_records, hs_code)
        self._export_csv(all_records, hs_code)

        logger.info("=" * 60)
        logger.info("DGCIS IMPORT COMPLETE")
        logger.info(f"  Queries made:   {self.stats['queries_made']}")
        logger.info(f"  Records found:  {self.stats['records_found']}")
        logger.info(f"  Years processed: {self.stats['years_processed']}")
        logger.info("=" * 60)

    def ensure_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trade_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hs_code TEXT,
                commodity TEXT,
                year TEXT,
                country TEXT,
                value_usd_million REAL,
                quantity REAL,
                unit TEXT,
                source TEXT DEFAULT 'dgcis',
                imported_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def _save_trade_data(self, records: list, hs_code: str):
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()

        for rec in records:
            commodity = rec.get("Commodity", "") or rec.get("Description", "")
            country = rec.get("Country", "") or rec.get("Country/Region", "")

            val_str = rec.get("Value US $ Million", "") or rec.get("US $ Million", "")
            qty_str = rec.get("Quantity", "") or rec.get("Quantity (Thousands)", "")

            value = 0
            quantity = 0
            try:
                value = float(re.sub(r"[^\d.-]", "", str(val_str)) or 0)
            except (ValueError, TypeError):
                pass
            try:
                quantity = float(re.sub(r"[^\d.-]", "", str(qty_str)) or 0)
            except (ValueError, TypeError):
                pass

            if not commodity and not country:
                continue

            try:
                conn.execute(
                    """INSERT INTO trade_data
                    (hs_code, commodity, year, country,
                     value_usd_million, quantity, source, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (hs_code, commodity, rec.get("year", ""), country,
                     value, quantity, "dgcis", now),
                )
            except Exception as e:
                logger.warning(f"Insert failed: {e}")

        conn.commit()
        conn.close()

    def _export_csv(self, records: list, hs_code: str):
        if not records:
            return
        csv_path = EXPORT_DIR / f"dgcis_import_{hs_code}_{datetime.now():%Y%m%d}.csv"
        all_keys = set()
        for rec in records:
            all_keys.update(rec.keys())
        fieldnames = sorted(all_keys)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        logger.info(f"CSV exported: {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="DGCIS Import Data Scraper")
    parser.add_argument("--hs", default="1511", help="HS code (default: 1511)")
    parser.add_argument("--year", type=int, default=None, help="Year (e.g. 2024)")
    parser.add_argument("--all-years", action="store_true", help="Fetch all years")
    parser.add_argument("--db", default="buyerhunter.db", help="Database path")
    args = parser.parse_args()

    importer = DGCISImporter(db_path=args.db)
    importer.run(hs_code=args.hs, year=args.year, all_years=args.all_years)


if __name__ == "__main__":
    main()
