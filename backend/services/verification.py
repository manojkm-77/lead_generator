"""
BuyerHunter AI — Verification Engine

Cross-checks company information across multiple public sources.
Verifies website, email, phone, address, company name.
Increases confidence when multiple sources agree.
"""

import re
import json
import logging
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "buyerhunter.db"


@dataclass
class VerificationResult:
    company_id: int
    confidence: int  # 0-100
    is_verified: bool
    verification_sources: list  # list of source names
    mismatches: list  # list of mismatch descriptions
    details: dict  # field-level verification


class VerificationEngine:
    """Cross-verifies company data across multiple public sources."""

    def __init__(self):
        pass

    def verify_company(self, company_id: int) -> Optional[VerificationResult]:
        """
        Verify a company by cross-checking its data across sources.

        Strategy:
        1. Load company record
        2. Find other records that match on name, website, email, or phone
        3. Cross-check each field
        4. Calculate confidence based on agreement
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        company = conn.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()

        if not company:
            conn.close()
            return None

        company = dict(company)

        # Find matching records from different sources
        matches = self._find_matches(conn, company)
        conn.close()

        if not matches:
            return VerificationResult(
                company_id=company_id,
                confidence=30,  # Base confidence for single-source data
                is_verified=False,
                verification_sources=[company.get("source", "unknown")],
                mismatches=[],
                details={"note": "Single source - no cross-verification possible"},
            )

        # Cross-check fields
        verification = self._cross_check(company, matches)

        return VerificationResult(
            company_id=company_id,
            confidence=verification["confidence"],
            is_verified=verification["confidence"] >= 60,
            verification_sources=verification["sources"],
            mismatches=verification["mismatches"],
            details=verification["details"],
        )

    def _find_matches(self, conn, company: dict) -> list[dict]:
        """Find records from other sources that match this company."""
        matches = []
        source = company.get("source", "")
        name = (company.get("company_name") or "").strip().lower()
        website = (company.get("website") or "").strip().lower()
        email = (company.get("email") or "").strip().lower()
        phone = (company.get("phone") or "").strip()

        # Match by website (strongest signal)
        if website:
            rows = conn.execute(
                """SELECT * FROM companies
                WHERE LOWER(website) = ? AND id != ? AND source != ?""",
                (website, company["id"], source),
            ).fetchall()
            matches.extend([dict(r) for r in rows])

        # Match by email (strong signal)
        if email:
            rows = conn.execute(
                """SELECT * FROM companies
                WHERE LOWER(email) = ? AND id != ? AND source != ?
                AND email IS NOT NULL AND email != ''""",
                (email, company["id"], source),
            ).fetchall()
            matches.extend([dict(r) for r in rows])

        # Match by phone (moderate signal)
        if phone and len(phone) >= 10:
            # Normalize phone for comparison
            phone_digits = re.sub(r"[^\d]", "", phone)
            rows = conn.execute(
                """SELECT * FROM companies
                WHERE id != ? AND source != ? AND phone IS NOT NULL AND phone != ''
                AND (REPLACE(REPLACE(REPLACE(phone, '-', ''), ' ', ''), '+', '') LIKE ?)""",
                (company["id"], source, f"%{phone_digits[-10:]}%"),
            ).fetchall()
            matches.extend([dict(r) for r in rows])

        # Match by fuzzy company name (weaker signal)
        if name and len(name) > 5:
            # Use LIKE for partial match
            words = name.split()
            if len(words) >= 2:
                search_term = f"%{words[0]}%"
                rows = conn.execute(
                    """SELECT * FROM companies
                    WHERE LOWER(company_name) LIKE ? AND id != ? AND source != ?""",
                    (search_term, company["id"], source),
                ).fetchall()
                for r in rows:
                    row = dict(r)
                    row_name = (row.get("company_name") or "").lower()
                    ratio = SequenceMatcher(None, name, row_name).ratio()
                    if ratio >= 0.6:
                        matches.append(row)

        # Deduplicate matches by id
        seen_ids = set()
        unique = []
        for m in matches:
            if m["id"] not in seen_ids:
                seen_ids.add(m["id"])
                unique.append(m)

        return unique

    def _cross_check(self, company: dict, matches: list[dict]) -> dict:
        """Cross-check company data against matches."""
        sources = set()
        sources.add(company.get("source", "unknown"))
        mismatches = []
        details = {}
        agreement_score = 0
        total_checks = 0

        for match in matches:
            sources.add(match.get("source", "unknown"))

            # Check company name similarity
            name1 = (company.get("company_name") or "").lower().strip()
            name2 = (match.get("company_name") or "").lower().strip()
            if name1 and name2:
                ratio = SequenceMatcher(None, name1, name2).ratio()
                total_checks += 1
                if ratio >= 0.7:
                    agreement_score += 1
                    details["name_match"] = f"Matched with {match.get('source')} (similarity: {ratio:.0%})"
                else:
                    mismatches.append(f"Name differs: '{name1}' vs '{name2}'")

            # Check website
            web1 = (company.get("website") or "").lower().strip().rstrip("/")
            web2 = (match.get("website") or "").lower().strip().rstrip("/")
            if web1 and web2:
                total_checks += 1
                if web1 == web2:
                    agreement_score += 1
                    details["website_match"] = "Confirmed across sources"
                else:
                    mismatches.append(f"Website differs: {web1} vs {web2}")

            # Check email
            email1 = (company.get("email") or "").lower().strip()
            email2 = (match.get("email") or "").lower().strip()
            if email1 and email2:
                total_checks += 1
                if email1 == email2:
                    agreement_score += 1
                    details["email_match"] = "Confirmed across sources"
                else:
                    mismatches.append(f"Email differs: {email1} vs {email2}")

            # Check phone
            phone1 = re.sub(r"[^\d]", "", company.get("phone") or "")
            phone2 = re.sub(r"[^\d]", "", match.get("phone") or "")
            if phone1 and phone2 and len(phone1) >= 10 and len(phone2) >= 10:
                total_checks += 1
                if phone1[-10:] == phone2[-10:]:
                    agreement_score += 1
                    details["phone_match"] = "Confirmed across sources"
                else:
                    mismatches.append(f"Phone differs: {phone1} vs {phone2}")

            # Check city
            city1 = (company.get("city") or "").lower().strip()
            city2 = (match.get("city") or "").lower().strip()
            if city1 and city2:
                total_checks += 1
                if city1 == city2 or city1 in city2 or city2 in city1:
                    agreement_score += 1
                    details["city_match"] = "Confirmed across sources"

            # Check state
            state1 = (company.get("state") or "").lower().strip()
            state2 = (match.get("state") or "").lower().strip()
            if state1 and state2:
                total_checks += 1
                if state1 == state2:
                    agreement_score += 1

        # Calculate confidence
        base_confidence = 30  # Single source
        if total_checks > 0:
            agreement_ratio = agreement_score / total_checks
            # Each confirming source adds confidence
            source_bonus = min(30, len(sources) * 10)
            check_bonus = int(40 * agreement_ratio)
            confidence = base_confidence + source_bonus + check_bonus
        else:
            confidence = base_confidence

        # Penalize for mismatches
        penalty = len(mismatches) * 5
        confidence = max(10, confidence - penalty)

        return {
            "confidence": min(100, confidence),
            "sources": list(sources),
            "mismatches": mismatches,
            "details": details,
            "agreement_score": agreement_score,
            "total_checks": total_checks,
        }

    def batch_verify(self, limit: int = 100, min_confidence: int = 0) -> dict:
        """Verify a batch of companies."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """SELECT id FROM companies
            WHERE confidence <= ? OR confidence = 0
            ORDER BY id DESC LIMIT ?""",
            (min_confidence, limit),
        ).fetchall()
        conn.close()

        verified = 0
        for row in rows:
            result = self.verify_company(row["id"])
            if result:
                self._save_verification(row["id"], result)
                verified += 1

        return {"verified": verified, "total": len(rows)}

    def _save_verification(self, company_id: int, result: VerificationResult):
        """Save verification results back to the company record."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """UPDATE companies SET
            confidence = ?, is_verified = ?
            WHERE id = ?""",
            (result.confidence, result.is_verified, company_id),
        )
        conn.commit()
        conn.close()
