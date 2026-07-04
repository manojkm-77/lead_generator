import json
import logging
import asyncio
from datetime import datetime

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

VALID_CATEGORIES = [
    "Food Manufacturer",
    "Restaurant",
    "Hotel",
    "Bakery",
    "Distributor",
    "Retail Chain",
    "Wholesaler",
    "Importer",
    "Exporter",
    "Unknown",
]

EDIBLE_OIL_KEYWORDS = [
    "oil", "edible", "cooking", "palm", "sunflower", "soybean",
    "mustard", "groundnut", "coconut", "canola", "rice bran",
    "refined", "vegetable", "frying", "food processing",
    "snack", "namkeen", "bakery", "confectionery",
]

HIGH_VOLUME_CATEGORIES = {
    "Food Manufacturer": 90,
    "Distributor": 85,
    "Wholesaler": 80,
    "Importer": 75,
    "Exporter": 70,
    "Bakery": 65,
    "Restaurant": 55,
    "Hotel": 50,
    "Retail Chain": 45,
    "Unknown": 20,
}

CONSUMPTION_ESTIMATES = {
    "Food Manufacturer": ("50-500 tonnes/year", "Monthly"),
    "Distributor": ("100-1000 tonnes/year", "Weekly"),
    "Wholesaler": ("50-500 tonnes/year", "Weekly"),
    "Importer": ("200-2000 tonnes/year", "Monthly"),
    "Exporter": ("100-1000 tonnes/year", "Monthly"),
    "Bakery": ("5-50 tonnes/year", "Weekly"),
    "Restaurant": ("1-10 tonnes/year", "Monthly"),
    "Hotel": ("2-20 tonnes/year", "Monthly"),
    "Retail Chain": ("10-100 tonnes/year", "Monthly"),
    "Unknown": ("Unknown", "Unknown"),
}


class AIQualifier:
    """Score companies for edible oil buying potential using Gemini API."""

    BATCH_SIZE = 5
    RETRY_ATTEMPTS = 2
    RETRY_DELAY = 1.0

    ENRICHED_PROMPT = """You are an expert B2B lead qualifier for the edible oil industry.

Analyze this company and determine their potential as an edible oil buyer.

Edible oils: Palm Oil, CP10, RBD Palm Olein, Sunflower Oil, Soybean Oil,
Rice Bran Oil, Canola Oil, Coconut Oil, Groundnut Oil, Mustard Oil.

Company Data:
- Name: {company_name}
- Website: {website}
- Industry: {industry}
- Products: {products}
- About: {about_us}
- Description: {description}
- Brands: {brands}
- Industries Served: {industries_served}
- City: {city}, {state}, {country}

Classify into ONE category:
Food Manufacturer, Restaurant, Hotel, Bakery, Distributor, Retail Chain,
Wholesaler, Importer, Exporter, Unknown

Estimate:
- Company size: Micro (1-10), Small (11-50), Medium (51-200), Large (201-1000), Enterprise (1000+)
- Potential oil usage: Low, Medium, High, Very High
- Annual consumption estimate in tonnes
- Buying frequency: Daily, Weekly, Monthly, Quarterly, Yearly
- Buyer confidence: 0-100

Scoring (0-100):
90-100: Major buyer (large manufacturer, distributor, 500+ tonnes/year)
70-89: Significant buyer (bakery chain, wholesaler, 100-500 tonnes/year)
50-69: Moderate buyer (restaurant chain, hotel group, 20-100 tonnes/year)
30-49: Occasional buyer (small retailer, local bakery, 5-20 tonnes/year)
0-29: Unlikely buyer or insufficient data

Respond with ONLY valid JSON:
{{
    "category": "...",
    "lead_score": 0,
    "confidence": 0,
    "reason": "...",
    "estimated_size": "...",
    "potential_oil_usage": "...",
    "estimated_annual_consumption": "...",
    "buying_frequency": "..."
}}"""

    BASIC_PROMPT = """You are an expert B2B lead qualifier for the edible oil industry.

Analyze this company and determine their potential as an edible oil buyer.

Company Data:
- Name: {company_name}
- Industry: {industry}
- Products: {products}
- City: {city}, {state}, {country}

Classify into ONE category:
Food Manufacturer, Restaurant, Hotel, Bakery, Distributor, Retail Chain,
Wholesaler, Importer, Exporter, Unknown

Estimate:
- Company size: Micro, Small, Medium, Large, Enterprise
- Potential oil usage: Low, Medium, High, Very High
- Annual consumption in tonnes
- Buying frequency: Daily, Weekly, Monthly, Quarterly, Yearly
- Buyer confidence: 0-100

Scoring (0-100):
90-100: Major buyer (500+ tonnes/year)
70-89: Significant buyer (100-500 tonnes/year)
50-69: Moderate buyer (20-100 tonnes/year)
30-49: Occasional buyer (5-20 tonnes/year)
0-29: Unlikely buyer

Respond with ONLY valid JSON:
{{
    "category": "...",
    "lead_score": 0,
    "confidence": 0,
    "reason": "...",
    "estimated_size": "...",
    "potential_oil_usage": "...",
    "estimated_annual_consumption": "...",
    "buying_frequency": "..."
}}"""

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self._model = None

    def _get_model(self):
        if self._model is None:
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._model = genai.GenerativeModel(
                    "gemini-2.0-flash",
                    generation_config=genai.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=600,
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                raise
        return self._model

    async def classify(self, company_data: dict) -> dict:
        """Classify a single company using Gemini API with fallback."""
        try:
            return await self._classify_with_ai(company_data)
        except Exception as e:
            logger.warning(f"AI classification failed for {company_data.get('company_name')}: {e}")
            return self._classify_with_rules(company_data)

    async def _classify_with_ai(self, company_data: dict) -> dict:
        model = self._get_model()
        has_enrichment = bool(company_data.get("about_us") or company_data.get("company_description"))

        prompt = self._build_enriched_prompt(company_data) if has_enrichment else self._build_basic_prompt(company_data)

        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                result = self._parse_response(response.text)
                if result:
                    return result
            except Exception as e:
                if attempt < self.RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise

        return self._classify_with_rules(company_data)

    def _build_enriched_prompt(self, data: dict) -> str:
        products = self._format_list(data.get("products"))
        brands = self._format_list(data.get("brands"))
        industries = self._format_list(data.get("industries_served"))

        return self.ENRICHED_PROMPT.format(
            company_name=data.get("company_name", "Unknown"),
            website=data.get("website", "N/A"),
            industry=data.get("industry", "N/A"),
            products=products or "N/A",
            about_us=(data.get("about_us") or "")[:1000],
            description=(data.get("company_description") or "")[:500],
            brands=brands or "N/A",
            industries_served=industries or "N/A",
            city=data.get("city", "N/A"),
            state=data.get("state", "N/A"),
            country=data.get("country", "India"),
        )

    def _build_basic_prompt(self, data: dict) -> str:
        products = self._format_list(data.get("products"))

        return self.BASIC_PROMPT.format(
            company_name=data.get("company_name", "Unknown"),
            industry=data.get("industry", "N/A"),
            products=products or "N/A",
            city=data.get("city", "N/A"),
            state=data.get("state", "N/A"),
            country=data.get("country", "India"),
        )

    def _format_list(self, value) -> str:
        if not value:
            return ""
        if isinstance(value, str) and value.startswith("["):
            try:
                items = json.loads(value)
                return ", ".join(str(i) for i in items[:10])
            except json.JSONDecodeError:
                return value
        if isinstance(value, list):
            return ", ".join(str(i) for i in value[:10])
        return str(value)

    def _parse_response(self, text: str) -> dict | None:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(text)
            if "category" not in data or "lead_score" not in data:
                return None

            return {
                "category": self._validate_category(data["category"]),
                "lead_score": max(0, min(100, int(data.get("lead_score", 0)))),
                "confidence": max(0, min(100, int(data.get("confidence", 50)))),
                "reason": str(data.get("reason", "")),
                "estimated_size": str(data.get("estimated_size", "Unknown")),
                "potential_oil_usage": str(data.get("potential_oil_usage", "Unknown")),
                "estimated_annual_consumption": str(data.get("estimated_annual_consumption", "Unknown")),
                "buying_frequency": str(data.get("buying_frequency", "Unknown")),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    def _validate_category(self, category: str) -> str:
        category = category.strip()
        for valid in VALID_CATEGORIES:
            if category.lower() == valid.lower():
                return valid
        return "Unknown"

    def _classify_with_rules(self, company_data: dict) -> dict:
        name = (company_data.get("company_name") or "").lower()
        industry = (company_data.get("industry") or "").lower()
        products = (company_data.get("products") or "").lower()
        about = (company_data.get("about_us") or "").lower()
        description = (company_data.get("company_description") or "").lower()
        combined = f"{name} {industry} {products} {about} {description}"

        # Determine category
        category = "Unknown"
        if any(w in combined for w in ["bakery", "baker", "pastry", "bread", "cake"]):
            category = "Bakery"
        elif any(w in combined for w in ["hotel", "resort", "inn", "hospitality"]):
            category = "Hotel"
        elif any(w in combined for w in ["restaurant", "cafe", "food court", "dining"]):
            category = "Restaurant"
        elif any(w in combined for w in ["distributor", "distribution"]):
            category = "Distributor"
        elif any(w in combined for w in ["wholesale", "wholesaler"]):
            category = "Wholesaler"
        elif any(w in combined for w in ["import", "importer"]):
            category = "Importer"
        elif any(w in combined for w in ["export", "exporter"]):
            category = "Exporter"
        elif any(w in combined for w in ["retail", "store", "supermarket", "mart"]):
            category = "Retail Chain"
        elif any(w in combined for w in ["manufactur", "factory", "production", "processing"]):
            category = "Food Manufacturer"

        # Score based on category + keyword match
        base_score = HIGH_VOLUME_CATEGORIES.get(category, 20)
        keyword_matches = sum(1 for kw in EDIBLE_OIL_KEYWORDS if kw in combined)
        keyword_bonus = min(30, keyword_matches * 5)
        lead_score = min(100, base_score + keyword_bonus)

        # Estimate size based on content
        size = "Small"
        if any(w in combined for w in ["enterprise", "multi-national", "global", "largest"]):
            size = "Enterprise"
        elif any(w in combined for w in ["large", "major", "leading", "top"]):
            size = "Large"
        elif any(w in combined for w in ["medium", "mid-size", "growing"]):
            size = "Medium"

        # Estimate oil usage
        oil_usage = "Low"
        if keyword_matches >= 5 or category in ("Food Manufacturer", "Distributor"):
            oil_usage = "High"
        elif keyword_matches >= 3 or category in ("Bakery", "Wholesaler"):
            oil_usage = "Medium"

        consumption, frequency = CONSUMPTION_ESTIMATES.get(category, ("Unknown", "Unknown"))

        return {
            "category": category,
            "lead_score": lead_score,
            "confidence": max(20, 70 - keyword_matches * 3),
            "reason": f"Rule-based: {category} with {keyword_matches} oil keywords, size={size}",
            "estimated_size": size,
            "potential_oil_usage": oil_usage,
            "estimated_annual_consumption": consumption,
            "buying_frequency": frequency,
        }

    async def classify_batch(self, companies: list[dict], batch_size: int = 5) -> list[dict]:
        """Classify multiple companies with rate limiting."""
        results = []
        for i in range(0, len(companies), batch_size):
            batch = companies[i : i + batch_size]
            tasks = [self.classify(c) for c in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for company, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Classification failed: {result}")
                    result = self._classify_with_rules(company)

                company["lead_score"] = result["lead_score"]
                company["industry"] = result["category"]
                company["ai_reason"] = result["reason"]
                company["ai_confidence"] = result["confidence"]
                company["ai_consumption"] = result["estimated_annual_consumption"]
                company["ai_frequency"] = result["buying_frequency"]
                company["estimated_size"] = result.get("estimated_size", "Unknown")
                company["potential_oil_usage"] = result.get("potential_oil_usage", "Unknown")
                company["estimated_annual_consumption"] = result.get("estimated_annual_consumption", "Unknown")
                company["_ai_classification"] = result
                results.append(company)

            if i + batch_size < len(companies):
                await asyncio.sleep(1.0)

        return results
