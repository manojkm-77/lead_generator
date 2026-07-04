"""
BuyerHunter AI — AI Buyer Summary Generator

Generates comprehensive buyer intelligence summaries using Gemini API.
"""

import json
import logging
import asyncio

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class BuyerSummaryGenerator:
    """Generates AI-powered buyer intelligence summaries."""

    SUMMARY_PROMPT = """You are a B2B sales intelligence analyst specializing in the edible oil industry.

Analyze this company and generate a comprehensive buyer intelligence report.

Company Data:
- Name: {company_name}
- Website: {website}
- Industry: {industry}
- Products: {products}
- About: {about_us}
- Description: {description}
- City: {city}, {state}, {country}
- Estimated Size: {size}
- Buyer Score: {score}/100
- Oil Detection: {oil_detection}

Generate a JSON report with:
1. company_summary: 2-3 sentence overview of the company
2. why_buyer: Why this company is a potential edible oil buyer (2-3 points)
3. recommended_pitch: Suggested sales pitch approach (2-3 sentences)
4. suggested_products: List of 3-5 specific oil products to recommend
5. risk_level: Low/Medium/High (payment risk, competition, etc.)
6. best_first_contact: Recommended approach for first contact
7. followup_strategy: Suggested follow-up strategy

Respond with ONLY valid JSON:
{{
    "company_summary": "...",
    "why_buyer": "...",
    "recommended_pitch": "...",
    "suggested_products": ["..."],
    "risk_level": "...",
    "best_first_contact": "...",
    "followup_strategy": "..."
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
                        temperature=0.2,
                        max_output_tokens=800,
                    ),
                )
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                raise
        return self._model

    async def generate(self, company_data: dict, product_detection: dict = None, buyer_score: dict = None) -> dict:
        """Generate AI buyer summary for a company."""
        try:
            return await self._generate_with_ai(company_data, product_detection, buyer_score)
        except Exception as e:
            logger.warning(f"AI summary failed for {company_data.get('company_name')}: {e}")
            return self._generate_fallback(company_data, product_detection, buyer_score)

    async def _generate_with_ai(self, company_data: dict, detection: dict, score: dict) -> dict:
        model = self._get_model()

        oil_text = ""
        if detection:
            high_prob = [k for k, v in detection.items() if k != "detection_notes" and v >= 0.3]
            oil_text = ", ".join(high_prob) if high_prob else "Limited detection"

        prompt = self.SUMMARY_PROMPT.format(
            company_name=company_data.get("company_name", "Unknown"),
            website=company_data.get("website", "N/A"),
            industry=company_data.get("industry", "N/A"),
            products=company_data.get("products", "N/A"),
            about_us=(company_data.get("about_us") or "")[:800],
            description=(company_data.get("company_description") or "")[:400],
            city=company_data.get("city", "N/A"),
            state=company_data.get("state", "N/A"),
            country=company_data.get("country", "India"),
            size=company_data.get("estimated_size", "Unknown"),
            score=score.get("buyer_score", 0) if score else 0,
            oil_detection=oil_text,
        )

        for attempt in range(2):
            try:
                response = await asyncio.to_thread(model.generate_content, prompt)
                return self._parse_response(response.text)
            except Exception as e:
                if attempt == 0:
                    await asyncio.sleep(1)
                else:
                    raise

        return self._generate_fallback(company_data, detection, score)

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            data = json.loads(text)
            suggested = data.get("suggested_products", [])
            if isinstance(suggested, list):
                suggested = json.dumps(suggested)
            return {
                "company_summary": str(data.get("company_summary", "")),
                "why_buyer": str(data.get("why_buyer", "")),
                "recommended_pitch": str(data.get("recommended_pitch", "")),
                "suggested_products": suggested,
                "risk_level": str(data.get("risk_level", "Medium")),
                "best_first_contact": str(data.get("best_first_contact", "")),
                "followup_strategy": str(data.get("followup_strategy", "")),
            }
        except (json.JSONDecodeError, ValueError):
            return self._generate_fallback({}, None, None)

    def _generate_fallback(self, company_data: dict, detection: dict, score: dict) -> dict:
        industry = company_data.get("industry") or "Unknown"
        name = company_data.get("company_name") or "The company"
        buyer_score = score.get("buyer_score", 0) if score else 0

        if buyer_score >= 70:
            priority = "high-value"
            pitch = f"{name} is a significant buyer in the {industry} sector. Focus on bulk pricing and long-term supply agreements."
            risk = "Low"
        elif buyer_score >= 40:
            priority = "moderate"
            pitch = f"{name} shows potential as an edible oil buyer. Start with sample orders and build relationship."
            risk = "Medium"
        else:
            priority = "developing"
            pitch = f"{name} may have limited oil requirements. Approach with competitive pricing for smaller volumes."
            risk = "Medium"

        products = []
        if detection:
            products = [k.replace("_", " ").title() for k, v in detection.items() if k != "detection_notes" and v >= 0.3]

        return {
            "company_summary": f"{name} operates in the {industry} sector.",
            "why_buyer": f"As a {industry.lower()}, {name} likely requires edible oils for their operations.",
            "recommended_pitch": pitch,
            "suggested_products": json.dumps(products[:5]) if products else json.dumps(["Palm Oil", "Sunflower Oil"]),
            "risk_level": risk,
            "best_first_contact": "Email introduction with product catalog, followed by phone call.",
            "followup_strategy": "Follow up within 3-5 business days. Offer samples if available.",
        }

    async def generate_batch(self, companies: list[dict], detections: dict = None, scores: dict = None) -> list[dict]:
        results = []
        for company in companies:
            cid = company.get("id")
            detection = (detections or {}).get(cid)
            score_data = (scores or {}).get(cid)
            summary = await self.generate(company, detection, score_data)
            summary["company_id"] = cid
            results.append(summary)
        return results
