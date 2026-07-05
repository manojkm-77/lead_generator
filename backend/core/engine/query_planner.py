"""
BuyerHunter V2 — Hybrid Query Planner

Combines the Deterministic Matrix (80%) with the AI Planner (20%)
into a single, unified query plan.

Entry point: HybridQueryPlanner.plan(query) → QueryPlanResult
"""

import logging

from backend.core.engine.intent_analyzer import IntentAnalyzer
from backend.core.engine.deterministic import DeterministicMatrix
from backend.core.engine.ai_planner import AIPlanner
from backend.core.schemas.intent import (
    SearchIntent,
    StructuredQuery,
    QueryPlanResult,
)

logger = logging.getLogger(__name__)


class HybridQueryPlanner:
    """
    Two-phase query planner:
      Phase 1 (80%): Deterministic matrix cross-product
      Phase 2 (20%): AI planner for non-obvious edge cases

    Returns a unified QueryPlanResult with both query sets.
    """

    def __init__(self, llm_client=None, ai_model: str = "gemini-2.0-flash"):
        self.analyzer = IntentAnalyzer()
        self.matrix = DeterministicMatrix()
        self.ai_planner = AIPlanner(llm_client=llm_client, model=ai_model)

    async def plan(
        self,
        query: str,
        *,
        max_deterministic: int = 300,
        max_ai: int = 50,
        include_tier2: bool = True,
        include_tier3: bool = False,
    ) -> QueryPlanResult:
        """
        Plan search queries for a raw user query.

        Steps:
          1. Extract structured intent (deterministic, no LLM)
          2. Generate deterministic queries via cross-product matrix
          3. Generate AI-expanded queries for edge cases
          4. Merge, deduplicate, and return unified plan

        Args:
            query: Raw user query string (e.g., "Palm Oil Buyers India")
            max_deterministic: Cap for deterministic queries
            max_ai: Cap for AI-expanded queries
            include_tier2: Include Tier 2 cities in deterministic expansion
            include_tier3: Include Tier 3 cities in deterministic expansion

        Returns:
            QueryPlanResult with intent, both query sets, and metadata
        """
        # Phase 1: Intent extraction (always deterministic)
        intent = self.analyzer.analyze(query)
        logger.info(
            f"Intent: product='{intent.product}', type='{intent.query_type}', "
            f"geo={'nationwide' if intent.geography_nationwide else intent.geography_state or intent.geography_city}, "
            f"confidence={intent.confidence}"
        )

        # Phase 2: Deterministic matrix (80%)
        deterministic_queries = self.matrix.generate(
            intent,
            max_queries=max_deterministic,
            include_tier2=include_tier2,
            include_tier3=include_tier3,
        )
        logger.info(f"Deterministic: {len(deterministic_queries)} queries generated")

        # Phase 3: AI planner (20%)
        ai_queries = await self.ai_planner.generate(
            intent,
            max_queries=max_ai,
        )
        logger.info(f"AI planner: {len(ai_queries)} queries generated")

        # Merge and deduplicate
        all_queries = self._merge_queries(deterministic_queries, ai_queries)

        # Compute metadata
        sources_covered = sorted(set(q.source for q in all_queries))
        states_covered = sorted(set(
            q.target_state for q in all_queries if q.target_state
        ))

        result = QueryPlanResult(
            intent=intent,
            deterministic_queries=deterministic_queries,
            ai_expanded_queries=ai_queries,
            total_queries=len(all_queries),
            sources_covered=sources_covered,
            states_covered=states_covered,
        )

        logger.info(
            f"Plan complete: {result.total_queries} total queries, "
            f"{len(sources_covered)} sources, {len(states_covered)} states"
        )
        return result

    def _merge_queries(
        self,
        deterministic: list[StructuredQuery],
        ai: list[StructuredQuery],
    ) -> list[StructuredQuery]:
        """
        Merge deterministic and AI queries, deduplicating by
        (query_string_lower, source). Deterministic wins on collision.
        """
        seen: set[tuple[str, str]] = set()
        merged: list[StructuredQuery] = []

        # Deterministic first (higher priority on collision)
        for q in deterministic:
            key = (q.query_string.lower(), q.source)
            if key not in seen:
                seen.add(key)
                merged.append(q)

        # AI queries fill gaps
        for q in ai:
            key = (q.query_string.lower(), q.source)
            if key not in seen:
                seen.add(key)
                merged.append(q)

        return merged

    def preview(self, query: str) -> dict:
        """
        Quick preview of intent extraction and deterministic queries.
        No LLM call. Useful for UI previews.
        """
        intent = self.analyzer.analyze(query)
        deterministic = self.matrix.generate(intent, max_queries=50)

        return {
            "intent": intent.model_dump(),
            "deterministic_count": len(deterministic),
            "sample_queries": [q.model_dump() for q in deterministic[:10]],
            "sources": list(set(q.source for q in deterministic)),
        }
