import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)


class SQLitePipeline:
    """Persist scraped items to SQLite database."""

    def __init__(self, db_path, crawler):
        self.db_path = db_path
        self.crawler = crawler
        self.items = []

    @classmethod
    def from_crawler(cls, crawler):
        db_path = crawler.settings.get("SQLITE_DB_PATH", "buyerhunter.db")
        return cls(db_path, crawler)

    def open_spider(self, spider=None):
        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
        try:
            self.conn.execute("ALTER TABLE companies ADD COLUMN confidence INTEGER DEFAULT 0")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                website TEXT,
                phone TEXT,
                whatsapp TEXT,
                email TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                country TEXT DEFAULT 'India',
                gst_number TEXT,
                industry TEXT,
                products TEXT,
                lead_score INTEGER DEFAULT 0,
                confidence INTEGER DEFAULT 0,
                source TEXT,
                crawl_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER,
                person_name TEXT,
                designation TEXT,
                email TEXT,
                phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id)
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                spider_name TEXT,
                start_time TEXT,
                end_time TEXT,
                pages_crawled INTEGER DEFAULT 0,
                companies_found INTEGER DEFAULT 0,
                duplicates_removed INTEGER DEFAULT 0,
                errors TEXT,
                status TEXT DEFAULT 'running'
            )
        """)
        self.conn.commit()
        self.open_log()

    @property
    def _spider(self):
        return getattr(self.crawler, "spider", None)

    def open_log(self):
        sp = self._spider
        sp_name = sp.name if sp else "unknown"
        cursor = self.conn.execute(
            "INSERT INTO crawl_logs (spider_name, start_time, pages_crawled, companies_found, duplicates_removed, status) VALUES (?, ?, 0, 0, 0, 'running')",
            (sp_name, datetime.now(timezone.utc).isoformat()),
        )
        self.log_id = cursor.lastrowid
        self.conn.commit()

    def _insert_item(self, data: dict):
        """Try inserting into v1 schema; fall back to v2 schema."""
        name = (data.get("company_name") or "").strip()
        phone = data.get("phone") or ""
        products = data.get("products")
        if isinstance(products, list):
            products = json.dumps(products)

        v1_cols = ["company_name", "website", "phone", "whatsapp", "email",
                   "address", "city", "state", "country", "gst_number",
                   "industry", "products", "lead_score", "confidence", "source", "crawl_date"]
        try:
            self.conn.execute(
                f"""INSERT INTO companies ({', '.join(v1_cols)})
                VALUES ({', '.join(['?'] * len(v1_cols))})""",
                (
                    name, data.get("website"), phone, data.get("whatsapp"),
                    data.get("email"), data.get("address"),
                    data.get("city"), data.get("state"),
                    data.get("country", "India"), data.get("gst_number"),
                    data.get("industry"), products,
                    data.get("lead_score", 0), data.get("confidence", 0),
                    data.get("source"), data.get("crawl_date"),
                ),
            )
        except Exception:
            # v2 schema fallback
            now = datetime.now(timezone.utc).isoformat()
            self.conn.execute(
                """INSERT INTO companies
                (canonical_name, website_url, gst_number, industry,
                 buyer_score, confidence, legal_status, company_tier, tier,
                 first_seen_source, first_seen_at, created_at, updated_at,
                 hq_city, hq_state, hq_address, hq_country, is_manufacturer,
                 is_importer, is_exporter, is_distributor, is_wholesaler, is_retailer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    name, data.get("website"), data.get("gst_number"),
                    data.get("industry"), data.get("lead_score", 0), 0,
                    "UNKNOWN", "UNKNOWN", "UNKNOWN",
                    data.get("source") or "scrapy", now, now, now,
                    data.get("city"), data.get("state"), data.get("address"),
                    data.get("country", "India"),
                    data.get("is_manufacturer", 0),
                    data.get("is_importer", 0),
                    data.get("is_exporter", 0),
                    data.get("is_distributor", 0),
                    data.get("is_wholesaler", 0),
                    data.get("is_retailer", 0),
                ),
            )

    def process_item(self, item, spider=None):
        data = dict(item)
        data.pop("_verification_issues", None)
        data.pop("_verified", None)

        name = (data.get("company_name") or "").strip().lower()
        phone = data.get("phone") or ""
        import sqlite3

        # Check for duplicates (handle both v1 and v2 schemas)
        try:
            existing = self.conn.execute(
                "SELECT id FROM companies WHERE LOWER(company_name) = ? AND phone = ?",
                (name, phone),
            ).fetchone()
        except Exception:
            try:
                existing = self.conn.execute(
                    "SELECT id FROM companies WHERE LOWER(canonical_name) = ?",
                    (name,),
                ).fetchone()
            except Exception:
                existing = None

        if existing:
            sp = self._spider
            if sp:
                sp.stats["duplicates"] += 1
            return item

        self._insert_item(data)
        self.conn.commit()
        return item

    def close_spider(self, spider=None):
        sp = self._spider or spider

        end_time = datetime.now(timezone.utc).isoformat()
        sp_name = sp.name if sp else "unknown"
        stats = sp.stats if sp else {"pages_crawled": 0, "companies_found": 0, "duplicates": 0, "errors": []}
        errors = json.dumps(stats.get("errors", []))

        self.conn.execute(
            """UPDATE crawl_logs SET
            end_time=?, pages_crawled=?, companies_found=?,
            duplicates_removed=?, errors=?, status=?
            WHERE id=?""",
            (
                end_time,
                stats["pages_crawled"],
                stats["companies_found"],
                stats["duplicates"],
                errors,
                "completed" if not stats["errors"] else "completed_with_errors",
                self.log_id,
            ),
        )
        self.conn.commit()
        self.conn.close()

        logger.info(
            f"[{sp_name}] Crawl complete: "
            f"{stats['pages_crawled']} pages, "
            f"{stats['companies_found']} companies, "
            f"{stats['duplicates']} duplicates"
        )


class CSVExportPipeline:
    """Export scraped items to CSV file."""

    def __init__(self, output_path, crawler):
        self.output_path = output_path
        self.crawler = crawler
        self.file = None
        self.writer = None

    @classmethod
    def from_crawler(cls, crawler):
        output_path = crawler.settings.get("CSV_OUTPUT_PATH", "exports/crawl_output.csv")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        return cls(output_path, crawler)

    @property
    def _spider(self):
        return getattr(self.crawler, "spider", None)

    def open_spider(self, spider=None):
        self.file = open(self.output_path, "w", newline="", encoding="utf-8")
        fieldnames = [
            "company_name", "website", "phone", "whatsapp", "email",
            "address", "city", "state", "country", "gst_number",
            "industry", "products", "lead_score", "confidence", "source", "crawl_date",
        ]
        self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
        self.writer.writeheader()

    def process_item(self, item, spider=None):
        data = dict(item)
        data.pop("_verification_issues", None)
        data.pop("_verified", None)

        products = data.get("products")
        if isinstance(products, list):
            products = ", ".join(products)

        row = {k: data.get(k, "") for k in self.writer.fieldnames}
        if row.get("products"):
            row["products"] = products
        self.writer.writerow(row)
        return item

    def close_spider(self, spider=None):
        sp = self._spider or spider
        if self.file:
            self.file.close()
        sp_name = sp.name if sp else "unknown"
        logger.info(f"[{sp_name}] CSV exported to {self.output_path}")
