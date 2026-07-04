import logging
from backend.utils.phone import normalize_phone
from backend.utils.email import validate_email
from backend.utils.text import normalize_text, title_case

logger = logging.getLogger(__name__)

CITY_STATE_MAP = {
    "mumbai": ("Mumbai", "Maharashtra"),
    "delhi": ("Delhi", "Delhi"),
    "new delhi": ("Delhi", "Delhi"),
    "bangalore": ("Bangalore", "Karnataka"),
    "bengaluru": ("Bangalore", "Karnataka"),
    "chennai": ("Chennai", "Tamil Nadu"),
    "hyderabad": ("Hyderabad", "Telangana"),
    "kolkata": ("Kolkata", "West Bengal"),
    "ahmedabad": ("Ahmedabad", "Gujarat"),
    "pune": ("Pune", "Maharashtra"),
    "jaipur": ("Jaipur", "Rajasthan"),
    "lucknow": ("Lucknow", "Uttar Pradesh"),
    "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "ludhiana": ("Ludhiana", "Punjab"),
    "vizag": ("Visakhapatnam", "Andhra Pradesh"),
    "visakhapatnam": ("Visakhapatnam", "Andhra Pradesh"),
    "nagpur": ("Nagpur", "Maharashtra"),
    "indore": ("Indore", "Madhya Pradesh"),
    "bhopal": ("Bhopal", "Madhya Pradesh"),
    "vadodara": ("Vadodara", "Gujarat"),
    "surat": ("Surat", "Gujarat"),
    "kanpur": ("Kanpur", "Uttar Pradesh"),
    "agra": ("Agra", "Uttar Pradesh"),
    "nashik": ("Nashik", "Maharashtra"),
}


class EnrichmentPipeline:
    def enrich(self, company_data: dict) -> dict:
        data = company_data.copy()

        data["phone"] = normalize_phone(data.get("phone"))
        data["whatsapp"] = normalize_phone(data.get("whatsapp")) or data.get("phone")
        data["email"] = validate_email(data.get("email"))

        data["company_name"] = title_case(data.get("company_name"))
        data["address"] = normalize_text(data.get("address"))
        data["city"] = title_case(data.get("city"))
        data["state"] = title_case(data.get("state"))

        city_lower = (data.get("city") or "").lower()
        if city_lower in CITY_STATE_MAP:
            data["city"], data["state"] = CITY_STATE_MAP[city_lower]

        if data.get("website"):
            url = data["website"].strip()
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            data["website"] = url

        return data

    def enrich_batch(self, companies: list[dict]) -> list[dict]:
        return [self.enrich(c) for c in companies]
