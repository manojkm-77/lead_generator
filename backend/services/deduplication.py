"""
BuyerHunter AI — Deduplication Engine

Merges companies using multiple matching criteria:
- Company Name (fuzzy)
- GST Number (exact)
- Website (exact)
- Email (exact)
- Phone (normalized)
- Address (fuzzy)

Keeps merge history. Updates existing records with richer data.
"""

import re
import json
import logging
import sqlite3
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "buyerhunter.db"


class DeduplicationEngine:
    """Multi-field deduplication with merge history."""

    def __init__(self):
        self._init_history_table()

    def _init_history_table(self):
        """Create merge history table if it doesn't exist."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS merge_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survivor_id INTEGER NOT NULL,
                merged_id INTEGER NOT NULL,
                merge_reason TEXT,
                merged_at REAL,
                data_before TEXT,
                data_after TEXT
            )
        """)
        conn.commit()
        conn.close()

    def deduplicate_batch(self, companies: list[dict]) -> dict:
        """
        Deduplicate a batch of companies against the database.

        Returns:
            {new_count, duplicate_count, merged_count}
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        new_count = 0
        duplicate_count = 0
        merged_count = 0

        for company in companies:
            name = (company.get("company_name") or "").strip()
            if not name or len(name) < 3:
                continue

            # Try to find existing match
            match = self._find_match(conn, company)

            if match:
                # Merge: update existing with richer data from new
                self._merge_records(conn, match, company)
                merged_count += 1
            else:
                # Insert new
                self._insert_company(conn, company)
                new_count += 1

        conn.commit()
        conn.close()

        logger.info(
            f"Dedup batch: {new_count} new, {duplicate_count} dupes, {merged_count} merged"
        )
        return {
            "new_count": new_count,
            "duplicate_count": duplicate_count,
            "merged_count": merged_count,
        }

    def _find_match(self, conn, company: dict) -> Optional[dict]:
        """Find a matching existing company using multiple criteria."""
        name = (company.get("company_name") or "").strip()
        name_lower = name.lower()
        gst = (company.get("gst_number") or "").strip()
        website = (company.get("website") or "").strip().lower().rstrip("/")
        email = (company.get("email") or "").strip().lower()
        phone = re.sub(r"[^\d]", "", company.get("phone") or "")

        # 1. Exact GST match (strongest)
        if gst and len(gst) >= 15:
            row = conn.execute(
                "SELECT * FROM companies WHERE gst_number = ?", (gst,)
            ).fetchone()
            if row:
                return dict(row)

        # 2. Exact website match (strong)
        if website and website.startswith("http"):
            row = conn.execute(
                "SELECT * FROM companies WHERE LOWER(REPLACE(REPLACE(website, 'https://', ''), 'http://', '')) = ?",
                (website.replace("https://", "").replace("http://", ""),),
            ).fetchone()
            if row:
                return dict(row)

        # 3. Exact email match (strong)
        if email and "@" in email:
            row = conn.execute(
                "SELECT * FROM companies WHERE LOWER(email) = ? AND email IS NOT NULL AND email != ''",
                (email,),
            ).fetchone()
            if row:
                return dict(row)

        # 4. Exact phone match (normalized, last 10 digits)
        if phone and len(phone) >= 10:
            phone_10 = phone[-10:]
            row = conn.execute(
                """SELECT * FROM companies
                WHERE phone IS NOT NULL AND phone != ''
                AND REPLACE(REPLACE(REPLACE(REPLACE(phone, '-', ''), ' ', ''), '+', ''), '+91', '') LIKE ?""",
                (f"%{phone_10}",),
            ).fetchone()
            if row:
                return dict(row)

        # 5. Fuzzy name match (moderate - use only if name is long enough)
        if name_lower and len(name_lower) >= 5:
            # First try exact name match
            row = conn.execute(
                "SELECT * FROM companies WHERE LOWER(company_name) = ?",
                (name_lower,),
            ).fetchone()
            if row:
                return dict(row)

            # Then try fuzzy match - find candidates by first word
            words = name_lower.split()
            if len(words) >= 2:
                search_term = f"%{words[0]}%"
                rows = conn.execute(
                    "SELECT * FROM companies WHERE LOWER(company_name) LIKE ? LIMIT 20",
                    (search_term,),
                ).fetchall()

                for row in rows:
                    existing_name = (dict(row).get("company_name") or "").lower()
                    ratio = SequenceMatcher(None, name_lower, existing_name).ratio()
                    if ratio >= 0.75:
                        return dict(row)

        return None

    def _merge_records(self, conn, existing: dict, new: dict):
        """
        Merge new data into existing record.
        Only overwrites NULL/empty fields - never overwrites existing data.
        """
        company_id = existing["id"]

        # Fields to potentially update (only if existing is empty)
        merge_fields = [
            "website", "phone", "whatsapp", "email", "address", "city", "state",
            "gst_number", "industry", "products", "about_us", "brands",
            "company_description", "contact_page", "procurement_info",
            "official_email", "sales_email", "procurement_email",
            "official_phone", "whatsapp_business",
            "factory_address", "office_address", "warehouse_address",
            "linkedin_url", "facebook_url",
            "fssai_number", "apeda_registration", "iec_code",
            "employees", "revenue", "turnover",
        ]

        updates = {}
        for field in merge_fields:
            existing_val = existing.get(field)
            new_val = new.get(field)

            # Only update if existing is empty and new has value
            if (not existing_val or existing_val == "" or existing_val == "None") and new_val:
                updates[field] = new_val

        # Update lead score if new is higher
        existing_score = existing.get("lead_score") or 0
        new_score = new.get("lead_score") or 0
        if new_score > existing_score:
            updates["lead_score"] = new_score

        # Update confidence
        updates["confidence"] = max(
            existing.get("confidence") or 0,
            new.get("confidence") or 30,
        )

        # Update source tracking
        existing_source = existing.get("source") or ""
        new_source = new.get("source") or ""
        if new_source and new_source not in existing_source:
            updates["source"] = f"{existing_source},{new_source}" if existing_source else new_source

        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [company_id]
            conn.execute(
                f"UPDATE companies SET {set_clause} WHERE id = ?",
                values,
            )

            # Record merge history
            conn.execute(
                """INSERT INTO merge_history
                (survivor_id, merged_id, merge_reason, merged_at, data_before, data_after)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    company_id,
                    new.get("id", 0),
                    json.dumps(list(updates.keys())),
                    __import__("time").time(),
                    json.dumps(existing, default=str),
                    json.dumps(updates, default=str),
                ),
            )

    def _insert_company(self, conn, company: dict):
        """Insert a new company record."""
        fields = [
            "company_name", "website", "phone", "whatsapp", "email",
            "address", "city", "state", "country", "gst_number", "industry",
            "products", "lead_score", "source", "crawl_date",
            "is_manufacturer", "is_importer", "is_exporter",
            "official_email", "sales_email", "procurement_email",
            "official_phone", "whatsapp_business",
        ]

        values = []
        for field in fields:
            val = company.get(field)
            if field == "country" and not val:
                val = "India"
            if field == "lead_score" and not val:
                val = 0
            values.append(val)

        placeholders = ", ".join(["?"] * len(fields))
        field_names = ", ".join(fields)

        conn.execute(
            f"INSERT INTO companies ({field_names}) VALUES ({placeholders})",
            values,
        )

    def get_merge_stats(self) -> dict:
        """Get deduplication statistics."""
        conn = sqlite3.connect(DB_PATH)

        total = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        merged = conn.execute("SELECT COUNT(*) FROM merge_history").fetchone()[0]

        conn.close()
        return {"total_companies": total, "total_merges": merged}
