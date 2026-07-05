"""
BuyerHunter V2 — AI Planner (20% Fallback)

A single LLM function that generates non-obvious procurement phrases
and edge-case queries the deterministic matrix misses.

Uses structured output (Pydantic model) for reliable parsing.
Falls back gracefully when no LLM key is configured.
"""

import json
import logging
from typing import Any

from backend.core.schemas.intent import SearchIntent, StructuredQuery

logger = logging.getLogger(__name__)

# ── Structured output schema for the LLM ────────────────────────────────────

AI_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "query_string": {"type": "string"},
                    "source": {"type": "string"},
                    "intent_label": {"type": "string"},
                },
                "required": ["query_string", "source", "intent_label"],
            },
        }
    },
    "required": ["queries"],
}

SYSTEM_PROMPT = """\
You are a B2B procurement search query generator for the Indian market.

Given a search intent, generate 10-20 non-obvious, high-value search queries
that a deterministic system would miss. Focus on:

1. **Procurement phrases**: "bulk purchase palm oil", "cooking oil toll packaging",
   "industrial oil procurement India"
2. **Industry-specific terms**: "vanaspati unit Gujarat", "soap noodles manufacturer",
   "oleochemical distributor Mumbai"
3. **Government/registry queries**: "FSSAI licensed food processor",
   "APEDA registered exporter", "GST registered edible oil dealer"
4. **Adjacent industries**: companies that USE the product but aren't in the
   primary category (e.g., restaurants buying cooking oil, bakeries buying shortening)
5. **Regional trade terms**: local names for products and business types

Available sources: indiamart, tradeindia, justdial, google_maps, fssai

Output JSON with a "queries" array. Each query has:
- query_string: the search query to run
- source: which crawler to use
- intent_label: human-readable label (e.g., "palm oil toll packaging in Gujarat")
"""


class AIPlanner:
    """
    LLM-powered query expansion. Generates non-obvious queries
    the deterministic matrix misses.

    Uses a single structured-output call per intent. Falls back
    to empty list if no LLM is configured or if the call fails.
    """

    def __init__(self, llm_client: Any = None, model: str = "gemini-2.0-flash"):
        """
        Args:
            llm_client: An async LLM client with a `generate_content` or
                        `chat.completions.create` method. If None, AI planning
                        is disabled and generate() returns [].
            model: Model identifier for the LLM.
        """
        self._client = llm_client
        self._model = model

    async def generate(
        self,
        intent: SearchIntent,
        *,
        max_queries: int = 50,
    ) -> list[StructuredQuery]:
        """
        Generate AI-expanded queries from a structured intent.

        Returns empty list if no LLM client is configured or on failure.
        """
        if self._client is None:
            logger.debug("AI Planner disabled: no LLM client configured")
            return []

        prompt = self._build_prompt(intent)

        try:
            raw = await self._call_llm(prompt)
            queries = self._parse_response(raw, intent)
            return queries[:max_queries]
        except Exception as e:
            logger.warning(f"AI Planner failed: {e}")
            return []

    def _build_prompt(self, intent: SearchIntent) -> str:
        """Construct the user prompt from the intent."""
        parts = [
            f"Product: {intent.product}",
        ]

        if intent.product_synonyms:
            parts.append(f"Also known as: {', '.join(intent.product_synonyms[:5])}")

        parts.append(f"Business type: {intent.business_type or 'any'}")

        if intent.geography_state:
            parts.append(f"State: {intent.geography_state}")
        if intent.geography_city:
            parts.append(f"City: {intent.geography_city}")
        if intent.geography_nationwide:
            parts.append("Geography: nationwide India")

        parts.append(f"Query type: {intent.query_type}")

        return "\n".join(parts)

    async def _call_llm(self, prompt: str) -> str:
        """Make the LLM call. Adapts to different client interfaces."""
        client = self._client

        # Try OpenAI-compatible interface first
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
                max_tokens=2000,
            )
            return response.choices[0].message.content or "{}"

        # Try Google Gemini interface
        if hasattr(client, "generate_content"):
            response = await client.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.7,
                    "max_output_tokens": 2000,
                    "response_mime_type": "application/json",
                    "response_schema": AI_QUERY_SCHEMA,
                },
                system_instruction=SYSTEM_PROMPT,
            )
            return response.text or "{}"

        raise ValueError(f"Unsupported LLM client type: {type(client)}")

    def _parse_response(
        self, raw: str, intent: SearchIntent
    ) -> list[StructuredQuery]:
        """Parse LLM JSON response into StructuredQuery objects."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("AI Planner returned invalid JSON")
            return []

        queries_raw = data.get("queries", [])
        if not isinstance(queries_raw, list):
            return []

        results: list[StructuredQuery] = []
        for item in queries_raw:
            if not isinstance(item, dict):
                continue
            q_str = item.get("query_string", "").strip()
            source = item.get("source", "indiamart").strip()
            label = item.get("intent_label", "").strip()

            if not q_str:
                continue

            # Validate source
            valid_sources = {"indiamart", "tradeindia", "justdial",
                             "google_maps", "fssai"}
            if source not in valid_sources:
                source = "indiamart"

            results.append(StructuredQuery(
                query_string=q_str,
                source=source,
                priority=7,  # AI queries get moderate priority
                target_state=intent.geography_state,
                target_city=intent.geography_city,
                intent_label=label or f"AI: {q_str}",
                generation_method="ai_expanded",
            ))

        # Deduplicate against deterministic queries (caller should merge)
        seen = set()
        unique: list[StructuredQuery] = []
        for q in results:
            key = q.query_string.lower()
            if key not in seen:
                seen.add(key)
                unique.append(q)

        return unique
