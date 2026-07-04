"""
BuyerHunter AI — Search Query Expansion Engine

Generates hundreds of intelligent search variations from a single user query.
Maps product keywords to industry verticals, business types, and locations.
"""

import logging
from itertools import product as cartesian_product

logger = logging.getLogger(__name__)

# ── Product → Industry mapping ────────────────────────────────────────────────
PRODUCT_TO_INDUSTRIES = {
    "palm oil": [
        "Edible Oil Manufacturer", "Oil Refinery", "Food Manufacturer",
        "Snack Manufacturer", "Bakery", "Soap Manufacturer", "Cosmetic Manufacturer",
        "Animal Feed Company", "Vanaspati Manufacturer", "FMCG Company",
        "Restaurant Chain", "Hotel", "Catering Company", "Institutional Catering",
    ],
    "sunflower oil": [
        "Edible Oil Manufacturer", "Oil Refinery", "Food Manufacturer",
        "Restaurant Chain", "Hotel", "FMCG Company", "Retail Chain",
    ],
    "soybean oil": [
        "Edible Oil Manufacturer", "Oil Refinery", "Food Manufacturer",
        "Animal Feed Company", "Restaurant Chain",
    ],
    "refined oil": [
        "Edible Oil Manufacturer", "Oil Refinery", "Food Manufacturer",
        "Distributor", "Wholesaler", "Retail Chain",
    ],
    "vegetable oil": [
        "Edible Oil Manufacturer", "Oil Refinery", "Food Manufacturer",
        "Snack Manufacturer", "Bakery", "Soap Manufacturer",
    ],
    "vanaspati": [
        "Vanaspati Manufacturer", "Food Manufacturer", "Bakery",
        "Restaurant Chain", "Sweet Manufacturer",
    ],
    "shortening": [
        "Bakery", "Food Manufacturer", "Snack Manufacturer", "Confectionery",
    ],
    "soap": [
        "Soap Manufacturer", "Detergent Company", "FMCG Company",
        "Personal Care Company", "Cosmetic Manufacturer",
    ],
    "detergent": [
        "Detergent Company", "FMCG Company", "Cleaning Products Company",
    ],
    "bakery": [
        "Bakery", "Food Manufacturer", "Confectionery", "Sweet Manufacturer",
        "Restaurant Chain", "Hotel",
    ],
    "snack": [
        "Snack Manufacturer", "Food Manufacturer", "FMCG Company",
        "Packaged Food Company",
    ],
    "confectionery": [
        "Confectionery", "Sweet Manufacturer", "Chocolate Manufacturer",
        "Food Manufacturer",
    ],
    "animal feed": [
        "Animal Feed Company", "Poultry Farm", "Dairy Farm",
        "Livestock Company", "Fishery",
    ],
    "cosmetic": [
        "Cosmetic Manufacturer", "Personal Care Company", "FMCG Company",
    ],
    "pharmaceutical": [
        "Pharmaceutical Company", "Medical Devices Company", "Healthcare Company",
    ],
}

# ── Business type keywords ────────────────────────────────────────────────────
BUSINESS_TYPES = {
    "buyers": ["Buyer", "Purchaser", "Procurement", "Importer"],
    "importers": ["Importer", "Import Agent", "Trading Company"],
    "exporters": ["Exporter", "Export House", "Trading Company"],
    "manufacturers": ["Manufacturer", "Producer", "Factory", "Refinery"],
    "distributors": ["Distributor", "Distribution Company", "Supply Chain"],
    "wholesalers": ["Wholesaler", "Wholesale Dealer", "Bulk Supplier"],
    "retailers": ["Retailer", "Retail Chain", "Store", "Supermarket"],
    "suppliers": ["Supplier", "Vendor", "Provider"],
    "processors": ["Processor", "Refiner", "Mill"],
}

# ── Indian states and major cities ────────────────────────────────────────────
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
    "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab",
    "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura",
    "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Chandigarh", "Puducherry", "Jammu & Kashmir", "Ladakh",
]

# Short name aliases for search
STATE_SHORT = {
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubli"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Varanasi", "Kanpur"],
    "Kerala": ["Kochi", "Trivandrum", "Kozhikode"],
    "Telangana": ["Hyderabad", "Warangal"],
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat"],
    "Bihar": ["Patna", "Gaya"],
    "Odisha": ["Bhubaneswar", "Cuttack"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur"],
    "Chhattisgarh": ["Raipur"],
    "Assam": ["Guwahati"],
    "Uttarakhand": ["Dehradun", "Haridwar"],
    "Jharkhand": ["Ranchi", "Jamshedpur"],
}

# ── Source-specific search templates ──────────────────────────────────────────
SOURCE_TEMPLATES = {
    "indiamart": {
        "url_pattern": "https://www.indiamart.com/search.html?ss={query}&src=se",
        "search_field": "ss",
    },
    "justdial": {
        "url_pattern": "https://www.justdial.com/{city}/{query}",
    },
    "tradeindia": {
        "url_pattern": "https://www.tradeindia.com/search.html?keyword={query}",
    },
    "yellowpages": {
        "url_pattern": "https://www.yellowpages.in/search?search_text={query}",
    },
    "exportersindia": {
        "url_pattern": "https://www.exportersindia.com/search.html?ss={query}",
    },
}


class QueryExpander:
    """Generates search variations from a user query."""

    def expand(self, query: str, max_queries: int = 200) -> list[dict]:
        """
        Expand a single query into multiple search variations.

        Returns list of dicts with:
          - query: the search string
          - source: recommended source spider
          - intent: what we're looking for
          - location: if location-specific
        """
        parsed = self._parse_query(query)
        variations = []

        # 1. Product-based variations
        for product in parsed["products"]:
            for biz_type in parsed["business_types"]:
                label = f"{product} {biz_type}"
                for source in self._best_sources(label):
                    variations.append({
                        "query": label,
                        "source": source,
                        "intent": f"{biz_type} for {product}",
                        "location": None,
                    })

        # 2. Industry-based variations
        for product in parsed["products"]:
            industries = PRODUCT_TO_INDUSTRIES.get(product.lower(), [])
            for industry in industries:
                variations.append({
                    "query": f"{industry} {parsed['location'] or 'India'}",
                    "source": self._best_sources(industry)[0],
                    "intent": f"Find {industry}",
                    "location": parsed["location"],
                })

        # 3. Location-specific variations
        if parsed["location"]:
            for product in parsed["products"]:
                for biz_type in parsed["business_types"][:3]:
                    variations.append({
                        "query": f"{product} {biz_type} {parsed['location']}",
                        "source": "indiamart",
                        "intent": f"{biz_type} in {parsed['location']}",
                        "location": parsed["location"],
                    })

        # 4. State-level expansion (if no specific location given)
        if not parsed["location"] or parsed["location"].lower() in ["india", "all"]:
            for state in INDIAN_STATES[:15]:  # Top 15 states
                for product in parsed["products"][:2]:
                    variations.append({
                        "query": f"{product} {parsed['business_types'][0]} {state}",
                        "source": "indiamart",
                        "intent": f"Find {parsed['business_types'][0]} in {state}",
                        "location": state,
                    })

        # 5. Generic variations
        for product in parsed["products"]:
            for suffix in ["buyers India", "importers India", "suppliers India",
                           "distributors India", "manufacturers India"]:
                variations.append({
                    "query": f"{product} {suffix}",
                    "source": "indiamart",
                    "intent": f"Find {suffix.split()[0]} of {product}",
                    "location": "India",
                })

        # Deduplicate
        seen = set()
        unique = []
        for v in variations:
            key = (v["query"].lower().strip(), v["source"])
            if key not in seen:
                seen.add(key)
                unique.append(v)

        logger.info(f"Expanded '{query}' into {len(unique)} search variations")
        return unique[:max_queries]

    def _parse_query(self, query: str) -> dict:
        """Parse user query into structured components."""
        query_lower = query.lower()

        # Extract products
        products = []
        for keyword in [
            "palm oil", "sunflower oil", "soybean oil", "mustard oil",
            "groundnut oil", "coconut oil", "rice bran oil", "refined oil",
            "vegetable oil", "vanaspati", "shortening", "bakery fat",
            "cp10", "cp8", "rbd palm olein", "palm stearin", "palm kernel oil",
            "oleochemical", "glycerine", "fatty acid",
            "soap", "detergent", "cosmetic", "pharmaceutical",
            "bakery", "snack", "confectionery", "chocolate",
            "animal feed", "poultry feed", "fish feed",
            "food", "edible oil",
        ]:
            if keyword in query_lower:
                products.append(keyword)

        if not products:
            # Try to extract any word that looks like a product
            words = query_lower.split()
            products = [" ".join(words[:2])] if len(words) >= 2 else [query_lower]

        # Extract business types
        business_types = []
        for btype, aliases in BUSINESS_TYPES.items():
            if btype in query_lower or any(a.lower() in query_lower for a in aliases):
                business_types.append(btype)

        if not business_types:
            business_types = ["buyers", "importers", "manufacturers", "distributors"]

        # Extract location
        location = None
        for state in INDIAN_STATES:
            if state.lower() in query_lower:
                location = state
                break
        if not location:
            for state, cities in STATE_SHORT.items():
                for city in cities:
                    if city.lower() in query_lower:
                        location = state
                        break
                if location:
                    break

        return {
            "products": products,
            "business_types": business_types,
            "location": location,
            "raw": query,
        }

    def _best_sources(self, query: str) -> list[str]:
        """Recommend best sources for a given query."""
        q = query.lower()
        sources = ["indiamart"]  # Always include IndiaMART

        if any(w in q for w in ["import", "export", "trade"]):
            sources.append("exportersindia")
        if any(w in q for w in ["distributor", "wholesal", "retail"]):
            sources.append("justdial")
        if any(w in q for w in ["manufactur", "factory", "refin"]):
            sources.append("tradeindia")
        if any(w in q for w in ["association", "federation"]):
            sources.append("tradeassociation")

        return sources
