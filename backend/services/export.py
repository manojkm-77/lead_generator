import csv
import json
import io
import sqlite3
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

EXPORT_DIR = Path("buyerhunter/exports")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def export_csv(companies: list[dict], filename: str | None = None) -> str:
    filename = filename or f"companies_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = EXPORT_DIR / filename

    if not companies:
        return str(filepath)

    headers = [
        "id", "company_name", "website", "phone", "whatsapp", "email",
        "address", "city", "state", "country", "gst_number", "industry",
        "products", "lead_score", "source", "crawl_date",
    ]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for company in companies:
            row = {k: company.get(k, "") for k in headers}
            writer.writerow(row)

    return str(filepath)


def export_excel(companies: list[dict], filename: str | None = None) -> str:
    filename = filename or f"companies_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"
    filepath = EXPORT_DIR / filename

    wb = Workbook()
    ws = wb.active
    ws.title = "Companies"

    headers = [
        "ID", "Company Name", "Website", "Phone", "WhatsApp", "Email",
        "Address", "City", "State", "Country", "GST Number", "Industry",
        "Products", "Lead Score", "Source", "Crawl Date",
    ]
    field_keys = [
        "id", "company_name", "website", "phone", "whatsapp", "email",
        "address", "city", "state", "country", "gst_number", "industry",
        "products", "lead_score", "source", "crawl_date",
    ]

    ws.append(headers)
    for company in companies:
        row = [company.get(k, "") for k in field_keys]
        ws.append(row)

    wb.save(filepath)
    return str(filepath)


def export_json(companies: list[dict], filename: str | None = None) -> str:
    filename = filename or f"companies_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = EXPORT_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(companies, f, indent=2, default=str)

    return str(filepath)


def export_sqlite_backup(source_db: str, filename: str | None = None) -> str:
    filename = filename or f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    filepath = EXPORT_DIR / filename

    conn = sqlite3.connect(source_db)
    backup_conn = sqlite3.connect(str(filepath))
    conn.backup(backup_conn)
    conn.close()
    backup_conn.close()

    return str(filepath)
