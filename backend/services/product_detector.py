"""
BuyerHunter AI — Product Detection Engine

Identifies which edible oils a company likely consumes
based on their website content and industry.
"""

import re
import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

OIL_PROFILES = {
    "palm_oil": {
        "name": "Palm Oil",
        "keywords": ["palm oil", "crude palm", "cpo", "palm kernel", "palm stearin"],
        "industries": ["Food Manufacturer", "Bakery", "Snack Manufacturer", "FMCG"],
        "base_weight": 0.7,
    },
    "rbd_palm_olein": {
        "name": "RBD Palm Olein",
        "keywords": ["rbd palm", "palm olein", "refined palm", "cooking oil", "frying oil"],
        "industries": ["Food Manufacturer", "Restaurant", "Hotel", "Catering"],
        "base_weight": 0.8,
    },
    "sunflower_oil": {
        "name": "Sunflower Oil",
        "keywords": ["sunflower oil", "sun oil", "sunola"],
        "industries": ["Food Manufacturer", "Retail", "Distribution"],
        "base_weight": 0.6,
    },
    "soybean_oil": {
        "name": "Soybean Oil",
        "keywords": ["soybean oil", "soya oil", "soy oil"],
        "industries": ["Food Manufacturer", "Restaurant"],
        "base_weight": 0.5,
    },
    "rice_bran_oil": {
        "name": "Rice Bran Oil",
        "keywords": ["rice bran oil", "rb oil", "健康油"],
        "industries": ["Food Manufacturer", "Health Food"],
        "base_weight": 0.4,
    },
    "mustard_oil": {
        "name": "Mustard Oil",
        "keywords": ["mustard oil", "sarson oil", "rai oil"],
        "industries": ["Food Manufacturer", "Restaurant", "Retail"],
        "base_weight": 0.5,
    },
    "groundnut_oil": {
        "name": "Groundnut Oil",
        "keywords": ["groundnut oil", "peanut oil", "moongphali oil"],
        "industries": ["Food Manufacturer", "Snack Manufacturer"],
        "base_weight": 0.5,
    },
    "coconut_oil": {
        "name": "Coconut Oil",
        "keywords": ["coconut oil", "copra oil", "nariyal oil"],
        "industries": ["Food Manufacturer", "Bakery", "Confectionery"],
        "base_weight": 0.4,
    },
    "vanaspati": {
        "name": "Vanaspati",
        "keywords": ["vanaspati", "hydrogenated oil", "dalda", "vegetable ghee"],
        "industries": ["Bakery", "Sweet Manufacturer", "Hotel"],
        "base_weight": 0.6,
    },
    "shortening": {
        "name": "Shortening",
        "keywords": ["shortening", "pastry fat", "puff pastry"],
        "industries": ["Bakery", "Confectionery"],
        "base_weight": 0.7,
    },
    "bakery_fat": {
        "name": "Bakery Fat",
        "keywords": ["bakery fat", "baking fat", "margarine", "butter alternative"],
        "industries": ["Bakery", "Confectionery", "Food Manufacturer"],
        "base_weight": 0.7,
    },
}


class ProductDetector:
    """Detects edible oil consumption patterns from company data."""

    def detect(self, company_data: dict) -> dict:
        """Analyze company data and return oil consumption probabilities."""
        text = self._build_analysis_text(company_data)
        industry = (company_data.get("industry") or "").lower()
        products = self._parse_products(company_data.get("products"))
        about = (company_data.get("about_us") or "").lower()
        description = (company_data.get("company_description") or "").lower()

        combined = f"{text} {industry} {' '.join(products)} {about} {description}"

        results = {}
        for oil_key, profile in OIL_PROFILES.items():
            probability = self._calculate_probability(combined, industry, profile)
            results[oil_key] = round(probability, 2)

        # Add detection notes
        results["detection_notes"] = self._generate_notes(combined, results)

        return results

    def _calculate_probability(self, text: str, industry: str, profile: dict) -> float:
        score = 0.0

        # Keyword matching
        keyword_hits = sum(1 for kw in profile["keywords"] if kw in text)
        if keyword_hits > 0:
            score += min(0.5, keyword_hits * 0.15)

        # Industry match
        for ind in profile["industries"]:
            if ind.lower() in industry:
                score += profile["base_weight"] * 0.4
                break

        # Contextual signals
        oil_mentions = len(re.findall(r"oil|cooking|frying|bakery|snack|food", text))
        if oil_mentions > 3:
            score += 0.1

        # Cap at 1.0
        return min(1.0, score)

    def _build_analysis_text(self, data: dict) -> str:
        parts = [
            data.get("company_name", ""),
            data.get("industry", ""),
            data.get("about_us", ""),
            data.get("company_description", ""),
            data.get("products", ""),
            data.get("brands", ""),
        ]
        return " ".join(str(p) for p in parts if p).lower()

    def _parse_products(self, products) -> list[str]:
        if not products:
            return []
        if isinstance(products, str):
            try:
                return json.loads(products)
            except json.JSONDecodeError:
                return [products]
        return products

    def _generate_notes(self, text: str, results: dict) -> str:
        high_prob = [
            OIL_PROFILES[k]["name"]
            for k, v in results.items()
            if k != "detection_notes" and v >= 0.5
        ]
        if high_prob:
            return f"High probability consumption: {', '.join(high_prob)}"
        medium_prob = [
            OIL_PROFILES[k]["name"]
            for k, v in results.items()
            if k != "detection_notes" and v >= 0.3
        ]
        if medium_prob:
            return f"Possible consumption: {', '.join(medium_prob)}"
        return "Low confidence - limited data available"

    def detect_batch(self, companies: list[dict]) -> list[dict]:
        results = []
        for company in companies:
            detection = self.detect(company)
            detection["company_id"] = company.get("id")
            results.append(detection)
        return results
