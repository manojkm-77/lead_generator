"""
BuyerHunter V2 — Intent Analyzer

Parses a raw user query string into a structured SearchIntent.
Uses deterministic regex + dictionary matching (no LLM needed for this step).
The AI planner handles edge cases later in the pipeline.
"""

import re
from backend.core.schemas.intent import SearchIntent

# ── Product dictionary (normalized key → synonyms) ───────────────────────────

PRODUCT_LEXICON: dict[str, list[str]] = {
    "palm oil": ["palm oil", "cp10", "cp8", "cp6", "cp0", "cpo",
                 "rbd palm olein", "palm olein", "palm stearin",
                 "palm kernel oil", "pko", "palm fraction",
                 "palm mid fraction", "pfad", "palm fatty acid",
                 "bleached palm oil", "deodorized palm oil"],
    "sunflower oil": ["sunflower oil", "sun oil", "sunflower refined oil"],
    "soybean oil": ["soybean oil", "soya oil", "soy oil", "soyabean oil"],
    "mustard oil": ["mustard oil", "sarson oil", "mustard seed oil"],
    "groundnut oil": ["groundnut oil", "peanut oil", "moongfali oil"],
    "coconut oil": ["coconut oil", "copra oil", "virgin coconut oil"],
    "rice bran oil": ["rice bran oil", "rice bran refined oil"],
    "cottonseed oil": ["cottonseed oil", "cotton seed oil"],
    "vegetable oil": ["vegetable oil", "mixed vegetable oil", "vanaspati",
                      "vegetable ghee", "vegetable shortening"],
    "edible oil": ["edible oil", "edible vegetable oil", "food grade oil"],
    "cooking oil": ["cooking oil", "frying oil", "deep fry oil",
                    "industrial cooking oil", "bulk cooking oil"],
    "refined oil": ["refined oil", "refined edible oil", "rbd oil"],
    "shortening": ["shortening", "bakery shortening", "puff pastry shortening",
                   "cake margarine", "industrial margarine"],
    "margarine": ["margarine", "table margarine", "bakery margarine"],
    "soap": ["soap", "toilet soap", "bath soap", "laundry soap",
             "soap noodles", "soap base"],
    "detergent": ["detergent", "detergent powder", "detergent cake",
                  "washing powder", "dishwash"],
    "bakery": ["bakery", "bakery products", "bread", "biscuit", "cookies",
               "cakes", "pastry", "rusk"],
    "snack": ["snack", "snacks", "namkeen", "chips", "wafers",
              "extruded snacks", "bhujia"],
    "confectionery": ["confectionery", "candy", "toffee", "sweets",
                      "chocolate", "cocoa"],
    "food processing": ["food", "food products", "food processing",
                        "packaged food", "processed food"],
    "dairy": ["dairy", "dairy products", "milk", "ghee", "butter",
              "cheese", "paneer", "yogurt"],
    "animal feed": ["animal feed", "poultry feed", "cattle feed",
                    "fish feed", "livestock feed"],
    "pharmaceutical": ["pharmaceutical", "pharma", "medicine", "drug",
                       "tablet", "capsule"],
    "chemical": ["chemical", "industrial chemical", "specialty chemical",
                 "oleochemical", "fatty acid", "glycerine", "surfactant"],
    "cosmetic": ["cosmetic", "cosmetics", "personal care", "skin care",
                 "hair care", "body lotion"],
    "restaurant": ["restaurant", "fine dining", "casual dining",
                   "cloud kitchen", "dhaba"],
    "hotel": ["hotel", "resort", "boutique hotel", "budget hotel"],
    "packaging": ["packaging", "flexible packaging", "rigid packaging",
                  "corrugated box", "carton box"],
    "textile": ["textile", "fabric", "garment", "apparel", "yarn"],
    "plastic": ["plastic", "plastic product", "pet", "hdpe", "ldpe", "pp"],
    "steel": ["steel", "stainless steel", "tmt bar", "steel pipe"],
}

# ── Business type patterns ──────────────────────────────────────────────────

BUSINESS_TYPE_PATTERNS: dict[str, list[str]] = {
    "buyer": ["buyer", "purchaser", "procurement", "buying",
              "requirement", "looking for", "need of"],
    "manufacturer": ["manufacturer", "producer", "factory", "refinery",
                     "manufacturing unit", "processing unit", "mill",
                     "plant", "maker"],
    "distributor": ["distributor", "distribution company", "stockist",
                    "dealer", "channel partner", "authorized distributor"],
    "wholesaler": ["wholesaler", "wholesale dealer", "bulk supplier",
                   "wholesale trader", "bulk seller"],
    "retailer": ["retailer", "retail chain", "store", "supermarket",
                 "hypermarket", "kirana store", "general store"],
    "importer": ["importer", "import agent", "import house",
                 "overseas buyer", "international buyer"],
    "exporter": ["exporter", "export house", "export agent",
                 "overseas supplier", "international supplier"],
    "trader": ["trader", "trading", "commodity trader", "merchant",
               "trading firm"],
    "supplier": ["supplier", "vendor", "provider", "raw material supplier"],
    "processor": ["processor", "refiner", "milling", "processing plant",
                  "processing facility"],
}

# ── Indian states & cities (for geography extraction) ────────────────────────

INDIAN_STATES = {
    "andhra pradesh": ["visakhapatnam", "vijayawada", "guntur", "nellore",
                       "kurnool", "rajamundry", "tirupati", "kakinada"],
    "arunachal pradesh": ["itanagar", "naharlagun", "pasighat"],
    "assam": ["guwahati", "silchar", "dibrugarh", "jorhat", "nagaon"],
    "bihar": ["patna", "gaya", "muzaffarpur", "bhagalpur", "darbhanga",
              "purnia", "begusarai"],
    "chhattisgarh": ["raipur", "bhilai", "bilaspur", "korba", "durg"],
    "goa": ["panaji", "margao", "vasco da gama", "mapusa", "ponda"],
    "gujarat": ["ahmedabad", "surat", "vadodara", "rajkot", "bhavnagar",
                "jamnagar", "junagadh", "gandhinagar", "anand", "nadiad",
                "morbi", "mehsana", "bharuch", "navsari", "bhuj"],
    "haryana": ["gurugram", "faridabad", "panipat", "karnal", "ambala",
                "hisar", "rohtak", "sonipat", "panchkula"],
    "himachal pradesh": ["shimla", "mandi", "dharamshala", "solan", "kullu"],
    "jharkhand": ["ranchi", "jamshedpur", "dhanbad", "bokaro", "deoghar"],
    "karnataka": ["bengaluru", "mysuru", "hubli", "mangaluru", "belgaum",
                  "davangere", "bellary", "shimoga", "tumkur"],
    "kerala": ["thiruvananthapuram", "kochi", "kozhikode", "thrissur",
               "malappuram", "kollam", "alappuzha", "palakkad", "kannur"],
    "madhya pradesh": ["bhopal", "indore", "jabalpur", "gwalior", "ujjain",
                       "sagar", "dewas", "satna"],
    "maharashtra": ["mumbai", "pune", "nagpur", "thane", "nashik",
                    "aurangabad", "solapur", "kolhapur", "amravati",
                    "navi mumbai", "kalyan", "jalgaon", "ahmednagar",
                    "sangli", "satara", "wardha"],
    "manipur": ["imphal", "bishnupur", "thoubal"],
    "meghalaya": ["shillong", "tura", "nongstoin"],
    "mizoram": ["aizawl", "lunglei", "champhai"],
    "nagaland": ["kohima", "dimapur", "mokokchung"],
    "odisha": ["bhubaneswar", "cuttack", "rourkela", "berhampur",
               "sambalpur", "puri", "balasore"],
    "punjab": ["ludhiana", "amritsar", "jalandhar", "patiala", "bathinda",
               "mohali", "pathankot", "hoshiarpur"],
    "rajasthan": ["jaipur", "jodhpur", "udaipur", "kota", "ajmer",
                  "bikaner", "bhilwara", "alwar", "bharatpur", "sikar",
                  "pali", "sri ganganagar"],
    "sikkim": ["gangtok", "namchi", "gyalshing"],
    "tamil nadu": ["chennai", "coimbatore", "madurai", "salem",
                   "tiruchirappalli", "tiruppur", "erode", "vellore",
                   "hosur", "kumbakonam"],
    "telangana": ["hyderabad", "warangal", "nizamabad", "karimnagar",
                  "khammam", "ramagundam", "suryapet"],
    "tripura": ["agartala", "udaipur", "dharmanagar"],
    "uttar pradesh": ["lucknow", "noida", "varanasi", "kanpur", "agra",
                      "meerut", "ghaziabad", "prayagraj", "bareilly",
                      "aligarh", "moradabad", "gorakhpur", "saharanpur"],
    "uttarakhand": ["dehradun", "haridwar", "haldwani", "rishikesh",
                    "roorkee", "rudrapur", "kashipur"],
    "west bengal": ["kolkata", "howrah", "durgapur", "siliguri", "asansol",
                    "bardhaman", "malda", "haldia", "darjeeling"],
    "delhi": ["new delhi", "dwarka", "rohini", "janakpuri", "saket",
              "karol bagh", "shahdara"],
    "puducherry": ["puducherry", "karaikal", "yanam", "mahe"],
    "jammu & kashmir": ["srinagar", "jammu", "anantnag", "baramulla"],
    "ladakh": ["leh", "kargil"],
}

# Build reverse lookup: city_lower → state
_CITY_TO_STATE: dict[str, str] = {}
for _state, _cities in INDIAN_STATES.items():
    for _city in _cities:
        _CITY_TO_STATE[_city] = _state


# ── Intent Analyzer ──────────────────────────────────────────────────────────

class IntentAnalyzer:
    """
    Deterministic intent extractor. No LLM calls.

    Parses raw query → SearchIntent with product, business_type,
    geography, and query_type classification.
    """

    def analyze(self, raw_query: str) -> SearchIntent:
        q = raw_query.lower().strip()

        product, synonyms = self._extract_product(q)
        business_type, bt_synonyms = self._extract_business_type(q)
        state, city, nationwide = self._extract_geography(q)
        query_type = self._classify_query_type(q, product, business_type)

        # Confidence heuristic
        confidence = 0.5
        if product != raw_query.strip():
            confidence += 0.2
        if business_type:
            confidence += 0.15
        if not nationwide:
            confidence += 0.1
        confidence = min(confidence, 1.0)

        return SearchIntent(
            raw_query=raw_query.strip(),
            product=product,
            product_synonyms=synonyms,
            business_type=business_type,
            business_type_synonyms=bt_synonyms,
            geography_state=state,
            geography_city=city,
            geography_nationwide=nationwide,
            query_type=query_type,
            confidence=round(confidence, 2),
        )

    # ── Private helpers ──────────────────────────────────────────────────────

    def _extract_product(self, query: str) -> tuple[str, list[str]]:
        """Match query against product lexicon. Returns (normalized_name, synonyms)."""
        # Try longest match first
        best_match = ""
        best_synonyms: list[str] = []

        for product_name, synonyms in sorted(
            PRODUCT_LEXICON.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if product_name in query:
                return product_name, synonyms

            # Check individual synonym matches
            for syn in synonyms:
                if syn.lower() in query:
                    return product_name, synonyms

        # Fallback: first meaningful word
        stop_words = {
            "the", "of", "in", "for", "and", "or", "to", "a", "an",
            "is", "are", "buy", "get", "find", "search", "list",
            "top", "best", "all", "india", "companies", "company",
            "near", "me", "with", "from",
        }
        words = [w for w in query.split() if w not in stop_words]
        if words:
            return words[0], []

        return query, []

    def _extract_business_type(self, query: str) -> tuple[str, list[str]]:
        """Extract business role from query."""
        for btype, patterns in sorted(
            BUSINESS_TYPE_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True
        ):
            for pattern in patterns:
                if pattern in query:
                    return btype, patterns
        return "", []

    def _extract_geography(self, query: str) -> tuple[str | None, str | None, bool]:
        """Extract state and/or city from query."""
        # Check cities first (more specific)
        for city, state in _CITY_TO_STATE.items():
            if city in query:
                return state, city.title(), False

        # Check states
        for state in INDIAN_STATES:
            if state in query:
                return state.title(), None, False

        # Check for "india" or no geography
        if "india" in query:
            return None, None, True

        return None, None, True

    def _classify_query_type(
        self, query: str, product: str, business_type: str
    ) -> str:
        """Classify the overall query type."""
        if business_type in ("buyer", "importer", "exporter", "trader"):
            return "product_buyer"
        if business_type in ("manufacturer", "processor"):
            return "industry_search"
        if business_type in ("retailer", "wholesaler", "distributor"):
            return "product_buyer"
        # Services
        if product in ("restaurant", "hotel"):
            return "service_search"
        return "general"
