import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import scrapy

logger = logging.getLogger(__name__)


class SQLitePipeline:
    """Persist scraped items to SQLite database."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.items = []

    @classmethod
    def from_crawler(cls, crawler):
        db_path = crawler.settings.get("SQLITE_DB_PATH", "buyerhunter.db")
        return cls(db_path)

    def open_spider(self, spider):
        import sqlite3
        self.conn = sqlite3.connect(self.db_path)
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
        self.open_log(spider)

    def open_log(self, spider):
        cursor = self.conn.execute(
            "INSERT INTO crawl_logs (spider_name, start_time, status) VALUES (?, ?, ?)",
            (spider.name, datetime.now(timezone.utc).isoformat(), "running"),
        )
        self.log_id = cursor.lastrowid
        self.conn.commit()

    def process_item(self, item, spider):
        data = dict(item)
        data.pop("_verification_issues", None)
        data.pop("_verified", None)

        # Check duplicate by name + phone
        name = (data.get("company_name") or "").strip().lower()
        phone = data.get("phone") or ""
        existing = self.conn.execute(
            "SELECT id FROM companies WHERE LOWER(company_name) = ? AND phone = ?",
            (name, phone),
        ).fetchone()

        if existing:
            spider.stats["duplicates"] += 1
            return item

        products = data.get("products")
        if isinstance(products, list):
            products = json.dumps(products)

        self.conn.execute(
            """INSERT INTO companies
            (company_name, website, phone, whatsapp, email, address,
             city, state, country, gst_number, industry, products,
             lead_score, source, crawl_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("company_name"),
                data.get("website"),
                data.get("phone"),
                data.get("whatsapp"),
                data.get("email"),
                data.get("address"),
                data.get("city"),
                data.get("state"),
                data.get("country", "India"),
                data.get("gst_number"),
                data.get("industry"),
                products,
                data.get("lead_score", 0),
                data.get("source"),
                data.get("crawl_date"),
            ),
        )
        self.conn.commit()
        return item

    def close_spider(self, spider):
        from scrapy.utils.python import global_object_name

        end_time = datetime.now(timezone.utc).isoformat()
        errors = json.dumps(spider.stats.get("errors", []))

        self.conn.execute(
            """UPDATE crawl_logs SET
            end_time=?, pages_crawled=?, companies_found=?,
            duplicates_removed=?, errors=?, status=?
            WHERE id=?""",
            (
                end_time,
                spider.stats["pages_crawled"],
                spider.stats["companies_found"],
                spider.stats["duplicates"],
                errors,
                "completed" if not spider.stats["errors"] else "completed_with_errors",
                self.log_id,
            ),
        )
        self.conn.commit()
        self.conn.close()

        logger.info(
            f"[{spider.name}] Crawl complete: "
            f"{spider.stats['pages_crawled']} pages, "
            f"{spider.stats['companies_found']} companies, "
            f"{spider.stats['duplicates']} duplicates"
        )


class CSVExportPipeline:
    """Export scraped items to CSV file."""

    def __init__(self, output_path):
        self.output_path = output_path
        self.file = None
        self.writer = None

    @classmethod
    def from_crawler(cls, crawler):
        output_path = crawler.settings.get("CSV_OUTPUT_PATH", "exports/crawl_output.csv")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        return cls(output_path)

    def open_spider(self, spider):
        self.file = open(self.output_path, "w", newline="", encoding="utf-8")
        fieldnames = [
            "company_name", "website", "phone", "whatsapp", "email",
            "address", "city", "state", "country", "gst_number",
            "industry", "products", "lead_score", "source", "crawl_date",
        ]
        self.writer = csv.DictWriter(self.file, fieldnames=fieldnames)
        self.writer.writeheader()

    def process_item(self, item, spider):
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

    def close_spider(self, spider):
        if self.file:
            self.file.close()
        logger.info(f"[{spider.name}] CSV exported to {self.output_path}")
