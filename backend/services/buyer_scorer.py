"""
BuyerHunter AI — Buyer Scoring Engine v2

8-factor composite scoring with sub-scores stored separately.
Each factor is 0-12.5 points, totaling 0-100.
"""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class BuyerMetrics:
    # Sub-scores (each 0-12.5, total 0-100)
    palm_oil_relevance: int = 0
    consumption_score: int = 0
    size_score: int = 0
    import_score: int = 0
    procurement_score: int = 0
    completeness_score: int = 0
    activity_score: int = 0
    opportunity_score: int = 0

    # Final composite
    buyer_score: int = 0

    # Derived metrics
    monthly_consumption: str = "Unknown"
    annual_consumption: str = "Unknown"
    buying_frequency: str = "Unknown"
    company_size: str = "Unknown"
    manufacturing_capacity: str = "Unknown"
    buyer_priority: str = "C"
    procurement_maturity: str = "Basic"
    lead_temperature: str = "Cold"

    def to_dict(self):
        return {
            "palm_oil_relevance": self.palm_oil_relevance,
            "consumption_score": self.consumption_score,
            "size_score": self.size_score,
            "import_score": self.import_score,
            "procurement_score": self.procurement_score,
            "completeness_score": self.completeness_score,
            "activity_score": self.activity_score,
            "opportunity_score": self.opportunity_score,
            "buyer_score": self.buyer_score,
        }


class BuyerScorer:
    """8-factor composite scoring engine."""

    # Industry base scores (0-12.5 scale)
    INDUSTRY_SCORES = {
        "Food Manufacturer": 12,
        "Snack / Food Manufacturer": 11,
        "Bakery": 10,
        "Oil Refinery": 11,
        "Edible Oil Trader": 9,
        "Distributor": 10,
        "Wholesaler": 8,
        "Importer": 9,
        "Exporter": 6,
        "Restaurant": 5,
        "Hotel": 6,
        "Retail Chain": 7,
        "FMCG / Personal Care": 7,
        "Animal Feed": 6,
        "Vanaspati Manufacturer": 10,
        "Soya Manufacturer": 8,
        "Sweet Manufacturer": 7,
        "Noodle / Instant Food": 7,
        "Food Processing Company": 8,
        "Unknown": 3,
    }

    # Oil types and their relevance to palm oil buying
    PALM_OIL_TYPES = [
        "palm_oil", "rbd_palm_olein", "vanaspati", "shortening", "bakery_fat",
    ]

    OTHER_OIL_TYPES = [
        "sunflower_oil", "soybean_oil", "rice_bran_oil", "mustard_oil",
        "groundnut_oil", "coconut_oil",
    ]

    def score(self, company_data: dict, product_detection: dict = None,
              contacts: list = None, enrichment_data: dict = None) -> BuyerMetrics:
        """Calculate 8-factor composite buyer score."""

        metrics = BuyerMetrics()

        # Factor 1: Palm Oil Relevance (0-12.5)
        metrics.palm_oil_relevance = self._score_palm_oil_relevance(product_detection or {})

        # Factor 2: Consumption Potential (0-12.5)
        metrics.consumption_score = self._score_consumption(company_data, product_detection or {})

        # Factor 3: Company Size (0-12.5)
        metrics.size_score = self._score_company_size(company_data)

        # Factor 4: Import Likelihood (0-12.5)
        metrics.import_score = self._score_import_likelihood(company_data)

        # Factor 5: Procurement Potential (0-12.5)
        metrics.procurement_score = self._score_procurement_potential(company_data, contacts or [])

        # Factor 6: Data Completeness (0-12.5)
        metrics.completeness_score = self._score_completeness(company_data)

        # Factor 7: Public Activity (0-12.5)
        metrics.activity_score = self._score_activity(company_data, enrichment_data or {})

        # Factor 8: Opportunity Score (0-12.5)
        metrics.opportunity_score = self._score_opportunity(company_data, product_detection or {}, contacts or [])

        # Composite total
        metrics.buyer_score = min(100, (
            metrics.palm_oil_relevance +
            metrics.consumption_score +
            metrics.size_score +
            metrics.import_score +
            metrics.procurement_score +
            metrics.completeness_score +
            metrics.activity_score +
            metrics.opportunity_score
        ))

        # Derive classification metrics
        self._derive_consumption(metrics, company_data, product_detection)
        self._derive_priority(metrics)
        self._derive_temperature(metrics, company_data, contacts)
        self._derive_maturity(metrics, company_data, contacts)
        self._derive_company_size(metrics, company_data)

        return metrics

    def _score_palm_oil_relevance(self, detection: dict) -> int:
        """How relevant is this company to palm oil specifically? (0-12.5)"""
        if not detection:
            return 2

        # Check palm oil specific types
        palm_hits = sum(
            1 for k in self.PALM_OIL_TYPES
            if detection.get(k, 0) >= 0.3
        )
        # Check other oil types (still relevant but less so)
        other_hits = sum(
            1 for k in self.OTHER_OIL_TYPES
            if detection.get(k, 0) >= 0.3
        )

        # Palm oil specific = high relevance
        if palm_hits >= 3:
            return 12
        if palm_hits >= 2:
            return 10
        if palm_hits >= 1:
            return 8
        # Other oils = moderate relevance
        if other_hits >= 3:
            return 6
        if other_hits >= 1:
            return 4
        return 2

    def _score_consumption(self, data: dict, detection: dict) -> int:
        """Estimated palm oil consumption potential. (0-12.5)"""
        industry = (data.get("industry") or "").lower()
        name = (data.get("company_name") or "").lower()
        products = (data.get("products") or "").lower()
        combined = f"{name} {products} {industry}"

        score = 3  # base

        # High consumption industries
        if any(w in combined for w in ["refin", "vanaspati", "hydrogenated", "vegetable ghee"]):
            score += 9  # Refineries = highest consumption
        elif any(w in combined for w in ["manufactur", "factory", "production", "processing"]):
            score += 7
        elif any(w in combined for w in ["bakery", "biscuit", "snack", "namkeen", "wafers"]):
            score += 6
        elif any(w in combined for w in ["hotel", "restaurant", "catering"]):
            score += 4
        elif any(w in combined for w in ["distribut", "wholesale", "dealer"]):
            score += 5
        elif any(w in combined for w in ["retail", "supermarket", "store"]):
            score += 3

        # Oil-specific keywords boost
        oil_keywords = ["palm oil", "cooking oil", "edible oil", "vegetable oil", "frying oil"]
        oil_hits = sum(1 for kw in oil_keywords if kw in combined)
        score += min(3, oil_hits)

        return min(12, score)

    def _score_company_size(self, data: dict) -> int:
        """Company size indicator. (0-12.5)"""
        score = 3  # base

        # Check employees
        employees = data.get("employees")
        if employees:
            if employees >= 1000:
                score += 9
            elif employees >= 200:
                score += 7
            elif employees >= 50:
                score += 5
            elif employees >= 10:
                score += 3

        # Check revenue/turnover
        revenue = (data.get("revenue") or data.get("turnover") or "").lower()
        if any(w in revenue for w in ["cr", "crore", "billion", "lakh crore"]):
            score += 3
        elif any(w in revenue for w in ["lakh", "million"]):
            score += 2

        # Check estimated size
        size = (data.get("estimated_size") or "").lower()
        if "enterprise" in size or "large" in size:
            score += 3
        elif "medium" in size:
            score += 2
        elif "small" in size:
            score += 1

        # Well-known company names
        name = (data.get("company_name") or "").lower()
        big_names = ["adani", "wilmar", "britannia", "itc", "parle", "haldiram", "balaji",
                     "dabur", "marico", "emami", "patanjali", "fortune", "allana", "cargill",
                     "bunge", "ruchi", "godrej"]
        if any(n in name for n in big_names):
            score += 2

        return min(12, score)

    def _score_import_likelihood(self, data: dict) -> int:
        """How likely is this company to import palm oil? (0-12.5)"""
        score = 2  # base

        name = (data.get("company_name") or "").lower()
        industry = (data.get("industry") or "").lower()
        products = (data.get("products") or "").lower()
        combined = f"{name} {industry} {products}"

        # Explicit import indicators
        if any(w in combined for w in ["import", "importer", "imported"]):
            score += 5

        # Export indicators (exporters often import raw materials)
        if any(w in combined for w in ["export", "exporter", "exported"]):
            score += 3

        # APEDA registered (government export registry = likely imports raw material)
        if data.get("apeda_registration") or "apeda" in (data.get("source") or "").lower():
            score += 3

        # GST registered (formal business = more likely to import)
        if data.get("gst_number"):
            score += 2

        # IEC code (Importer Exporter Code = definitely imports/exports)
        if data.get("iec_code"):
            score += 4

        return min(12, score)

    def _score_procurement_potential(self, data: dict, contacts: list) -> int:
        """Procurement infrastructure and contacts. (0-12.5)"""
        score = 2  # base

        # Has website with procurement info
        if data.get("website"):
            score += 2
        if data.get("procurement_info"):
            score += 2
        if data.get("contact_page"):
            score += 1

        # Has procurement contacts
        if contacts:
            procurement_titles = ["procurement", "purchase", "buying", "supply chain",
                                  "commercial", "sourcing", "vendor"]
            proc_contacts = [
                c for c in contacts
                if any(t in (getattr(c, "designation", "") or "").lower()
                       for t in procurement_titles)
            ]
            if proc_contacts:
                score += 4
            elif len(contacts) >= 2:
                score += 2
            elif len(contacts) >= 1:
                score += 1

        # Has official contact channels
        if data.get("official_email") or data.get("sales_email"):
            score += 1
        if data.get("official_phone") or data.get("whatsapp_business"):
            score += 1

        return min(12, score)

    def _score_completeness(self, data: dict) -> int:
        """How complete is the company profile? (0-12.5)"""
        important_fields = [
            "company_name", "website", "email", "phone", "address",
            "city", "state", "industry", "products", "gst_number",
            "official_email", "official_phone",
        ]
        filled = sum(1 for f in important_fields if data.get(f))
        ratio = filled / len(important_fields)
        return int(12.5 * ratio)

    def _score_activity(self, data: dict, enrichment: dict) -> int:
        """Public activity and online presence. (0-12.5)"""
        score = 2  # base

        # Website quality
        if data.get("website"):
            score += 2
        if data.get("about_us") or data.get("company_description"):
            score += 1
        if data.get("brands"):
            score += 1

        # Social media presence
        if data.get("linkedin_url"):
            score += 2
        if data.get("facebook_url"):
            score += 1
        if data.get("google_rating"):
            score += 1
            if data["google_rating"] >= 4.0:
                score += 1

        # Enrichment data
        if enrichment.get("enriched_at"):
            score += 1

        # Products listed
        if data.get("products"):
            products = data["products"]
            if isinstance(products, str):
                try:
                    products = json.loads(products)
                except:
                    products = [products]
            if isinstance(products, list) and len(products) >= 3:
                score += 1

        return min(12, score)

    def _score_opportunity(self, data: dict, detection: dict, contacts: list) -> int:
        """Overall opportunity for Swastik Eximp. (0-12.5)"""
        score = 3  # base

        # High palm oil relevance = high opportunity
        palm_hits = sum(
            1 for k in self.PALM_OIL_TYPES
            if detection.get(k, 0) >= 0.3
        )
        if palm_hits >= 2:
            score += 4
        elif palm_hits >= 1:
            score += 2

        # Has contact info = can reach them
        if data.get("email") or data.get("official_email"):
            score += 2
        if data.get("phone") or data.get("official_phone"):
            score += 1

        # Gujarat location (closer to Swastik Eximp's market)
        state = (data.get("state") or "").lower()
        if "gujarat" in state:
            score += 1

        # Has website = can verify and approach
        if data.get("website"):
            score += 1

        return min(12, score)

    def _derive_consumption(self, metrics: BuyerMetrics, data: dict, detection: dict):
        """Estimate consumption based on score and industry."""
        score = metrics.buyer_score
        industry = (data.get("industry") or "").lower()

        if score >= 70:
            metrics.monthly_consumption = "50-200 tonnes"
            metrics.annual_consumption = "600-2400 tonnes"
            metrics.buying_frequency = "Weekly"
        elif score >= 50:
            metrics.monthly_consumption = "10-50 tonnes"
            metrics.annual_consumption = "120-600 tonnes"
            metrics.buying_frequency = "Monthly"
        elif score >= 35:
            metrics.monthly_consumption = "2-10 tonnes"
            metrics.annual_consumption = "24-120 tonnes"
            metrics.buying_frequency = "Monthly"
        else:
            metrics.monthly_consumption = "<2 tonnes"
            metrics.annual_consumption = "<24 tonnes"
            metrics.buying_frequency = "Quarterly"

        # Refineries consume much more
        if "refin" in industry:
            metrics.monthly_consumption = "200-1000 tonnes"
            metrics.annual_consumption = "2400-12000 tonnes"
            metrics.buying_frequency = "Weekly"

    def _derive_priority(self, metrics: BuyerMetrics):
        score = metrics.buyer_score
        if score >= 70:
            metrics.buyer_priority = "A"
        elif score >= 50:
            metrics.buyer_priority = "B"
        elif score >= 35:
            metrics.buyer_priority = "C"
        else:
            metrics.buyer_priority = "D"

    def _derive_temperature(self, metrics: BuyerMetrics, data: dict, contacts: list):
        score = metrics.buyer_score
        has_contact = bool(data.get("email") or data.get("official_email") or
                          data.get("phone") or data.get("official_phone"))
        has_procurement = any(
            c for c in (contacts or [])
            if any(t in (getattr(c, "designation", "") or "").lower()
                   for t in ["procurement", "purchase", "supply chain"])
        )

        if score >= 70 and has_contact:
            metrics.lead_temperature = "Hot"
        elif score >= 50 and (has_contact or has_procurement):
            metrics.lead_temperature = "Warm"
        elif score >= 35:
            metrics.lead_temperature = "Warm"
        else:
            metrics.lead_temperature = "Cold"

    def _derive_maturity(self, metrics: BuyerMetrics, data: dict, contacts: list):
        has_procurement = any(
            c for c in (contacts or [])
            if any(t in (getattr(c, "designation", "") or "").lower()
                   for t in ["procurement", "purchase", "supply chain"])
        )
        if has_procurement and data.get("website"):
            metrics.procurement_maturity = "Advanced"
        elif data.get("website") or data.get("phone"):
            metrics.procurement_maturity = "Developing"
        else:
            metrics.procurement_maturity = "Basic"

    def _derive_company_size(self, metrics: BuyerMetrics, data: dict):
        employees = data.get("employees")
        if employees:
            if employees >= 1000:
                metrics.company_size = "Enterprise"
            elif employees >= 200:
                metrics.company_size = "Large"
            elif employees >= 50:
                metrics.company_size = "Medium"
            elif employees >= 10:
                metrics.company_size = "Small"
            else:
                metrics.company_size = "Micro"
        else:
            # Infer from name/industry
            name = (data.get("company_name") or "").lower()
            big_names = ["adani", "wilmar", "britannia", "itc", "parle", "dabur", "marico"]
            if any(n in name for n in big_names):
                metrics.company_size = "Large"
            else:
                metrics.company_size = "Unknown"

        # Manufacturing capacity
        score = metrics.buyer_score
        if score >= 70:
            metrics.manufacturing_capacity = "High"
        elif score >= 50:
            metrics.manufacturing_capacity = "Medium"
        elif score >= 35:
            metrics.manufacturing_capacity = "Low-Medium"
        else:
            metrics.manufacturing_capacity = "Low"
