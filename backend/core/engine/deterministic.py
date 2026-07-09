"""
BuyerHunter V2 — Deterministic Query Matrix (80%)

Programmatically maps target products against:
  1. Structural dictionary of Indian Tier 1/2/3 districts, states
  2. Business keywords (wholesaler, refinery, manufacturer, etc.)
  3. Source-specific URL patterns

Produces the bulk of search queries without any LLM calls.
"""

from itertools import product as cartesian

from backend.core.schemas.intent import SearchIntent, StructuredQuery

# ── Source definitions ───────────────────────────────────────────────────────

SOURCE_CONFIGS: dict[str, dict] = {
    "indiamart": {
        "priority": 10,
        "description": "India's largest B2B marketplace",
    },
    "justdial": {
        "priority": 9,
        "description": "Local business directory",
    },
    "tradeindia": {
        "priority": 8,
        "description": "B2B trade directory",
    },
    "exportersindia": {
        "priority": 7,
        "description": "Export/import trade directory",
    },
    "google_maps": {
        "priority": 6,
        "description": "Business listings on Google Maps",
    },
    "yellowpages": {
        "priority": 5,
        "description": "Yellow Pages business directory",
    },
    "fssai": {
        "priority": 4,
        "description": "FSSAI license registry",
    },
}

# ── Business suffixes per type ──────────────────────────────────────────────

TYPE_SUFFIXES: dict[str, list[str]] = {
    "buyer": ["buyer", "purchaser", "procurement"],
    "manufacturer": ["manufacturer", "producer", "factory", "refinery",
                     "processing unit", "mill", "plant"],
    "distributor": ["distributor", "dealer", "stockist", "channel partner"],
    "wholesaler": ["wholesaler", "wholesale dealer", "bulk supplier"],
    "retailer": ["retailer", "store", "supermarket"],
    "importer": ["importer", "import house", "trading company"],
    "exporter": ["exporter", "export house", "trading company"],
    "trader": ["trader", "trading firm", "merchant"],
    "supplier": ["supplier", "vendor", "raw material supplier"],
    "processor": ["processor", "refiner", "processing plant"],
}

# ── Tier 1 cities (always included for nationwide) ──────────────────────────

TIER1_CITIES = [
    "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Surat", "Jaipur",
]

# ── Source routing rules ────────────────────────────────────────────────────

# Priority order: working sources first, IndiaMART last (rate-limited)
SOURCE_CYCLE = ["tradeindia", "justdial", "exportersindia", "google_maps", "yellowpages", "indiamart"]
_route_counter: dict[str, int] = {}

def _route_to_source(
    query_lower: str,
    business_type: str,
    product: str,
) -> str:
    """Distribute queries across ALL available sources.
    Each call rotates through sources so every source gets traffic.
    Priority: working sources first, IndiaMART last (aggressive rate limiting).
    """
    global _route_counter
    key = f"{business_type}:{product}"
    _route_counter.setdefault(key, 0)
    _route_counter[key] += 1
    idx = _route_counter[key] % len(SOURCE_CYCLE)
    return SOURCE_CYCLE[idx]


class DeterministicMatrix:
    """
    Generates search queries via programmatic cross-product of:
      products × business_types × geographies × sources

    This covers ~80% of all useful queries without any LLM call.
    """

    def generate(
        self,
        intent: SearchIntent,
        *,
        max_queries: int = 300,
        include_tier2: bool = True,
        include_tier3: bool = False,
    ) -> list[StructuredQuery]:
        """
        Generate deterministic queries from a structured intent.

        Args:
            intent: Structured intent from IntentAnalyzer
            max_queries: Hard cap on output count
            include_tier2: Include Tier 2 cities
            include_tier3: Include Tier 3 cities

        Returns:
            List of StructuredQuery with generation_method='deterministic'
        """
        product = intent.product
        product_terms = [product] + intent.product_synonyms[:3]

        # Business type variations
        btype = intent.business_type
        if btype in TYPE_SUFFIXES:
            bt_variants = TYPE_SUFFIXES[btype][:4]
        elif btype:
            bt_variants = [btype]
        else:
            bt_variants = ["buyer", "manufacturer", "supplier", "trader"]

        # Geography
        locations = self._build_location_list(intent, include_tier2, include_tier3)

        queries: list[StructuredQuery] = []

        # Cross-product: product_terms × bt_variants × locations
        # Use local counter to ensure proper source rotation
        local_counter = 0
        for prod in product_terms[:5]:
            for bt in bt_variants:
                for loc in locations:
                    q_str = f"{prod} {bt}"
                    if loc:
                        q_str += f" {loc}"

                    # Use local counter for consistent source rotation
                    source = SOURCE_CYCLE[local_counter % len(SOURCE_CYCLE)]
                    local_counter += 1
                    priority = SOURCE_CONFIGS[source]["priority"]

                    label = f"{prod} {bt}"
                    if loc:
                        label += f" in {loc}"

                    queries.append(StructuredQuery(
                        query_string=q_str.strip(),
                        source=source,
                        priority=priority,
                        target_state=loc if loc and loc in self._all_states() else None,
                        target_city=loc if loc and loc not in self._all_states() else None,
                        intent_label=label,
                        generation_method="deterministic",
                    ))

        # Deduplicate
        seen = set()
        unique: list[StructuredQuery] = []
        for q in queries:
            key = (q.query_string.lower(), q.source)
            if key not in seen:
                seen.add(key)
                unique.append(q)

        # Ensure source diversity: interleave sources instead of sorting by priority
        # Group by source
        by_source: dict[str, list[StructuredQuery]] = {}
        for q in unique:
            by_source.setdefault(q.source, []).append(q)

        # Round-robin through sources to ensure diversity
        interleaved: list[StructuredQuery] = []
        source_lists = list(by_source.values())
        max_per_source = (max_queries // len(source_lists)) + 1 if source_lists else max_queries
        for i in range(max_per_source):
            for src_list in source_lists:
                if i < len(src_list):
                    interleaved.append(src_list[i])

        return interleaved[:max_queries]

    # ── Private helpers ──────────────────────────────────────────────────────

    def _build_location_list(
        self,
        intent: SearchIntent,
        include_tier2: bool,
        include_tier3: bool,
    ) -> list[str]:
        """Build list of locations based on intent geography."""
        if intent.geography_city:
            # Specific city query — only that city
            return [intent.geography_city]

        if intent.geography_state:
            # State-level — state + Tier 1 cities in that state
            return self._state_and_cities(intent.geography_state)

        if intent.geography_nationwide:
            # Nationwide — all states + Tier 1 cities
            locs = [None]  # type: ignore[list-item]
            locs.extend(TIER1_CITIES)
            if include_tier2:
                locs.extend(self._tier2_cities())
            return locs  # type: ignore[return-value]

        return [None]  # type: ignore[list-item]

    def _state_and_cities(self, state: str) -> list[str]:
        """Return state name + Tier 1 cities within that state."""
        from backend.core.engine.intent_analyzer import INDIAN_STATES

        state_lower = state.lower()
        cities = INDIAN_STATES.get(state_lower, [])[:5]
        return [state] + cities

    def _tier2_cities(self) -> list[str]:
        """Major Tier 2 cities across India."""
        return [
            "Lucknow", "Nagpur", "Indore", "Bhopal", "Patna",
            "Vadodara", "Coimbatore", "Kochi", "Visakhapatnam",
            "Thiruvananthapuram", "Ludhiana", "Agra", "Nashik",
            "Meerut", "Rajkot", "Varanasi", "Srinagar", "Aurangabad",
            "Dhanbad", "Amritsar", "Allahabad", "Ranchi", "Howrah",
            "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur", "Madurai",
            "Raipur", "Kota", "Guwahati", "Chandigarh",
        ]

    def _all_states(self) -> set[str]:
        """Return set of all Indian state names."""
        from backend.core.engine.intent_analyzer import INDIAN_STATES
        return {s.title() for s in INDIAN_STATES}
