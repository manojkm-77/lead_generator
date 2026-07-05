"""
BuyerHunter AI — Lead Discovery Pipeline v3

Delegates to the SearchPlanner for the full discovery flow.
Provides backward-compatible API for existing routes.
"""

import logging
from typing import Optional

from backend.services.search_planner import (
    SearchPlanner,
    get_pipeline_progress,
    get_all_pipelines,
    pipeline_event_stream,
)

logger = logging.getLogger(__name__)

# Create global planner instance
_planner = SearchPlanner()


def get_pipeline_progress(run_id: str) -> Optional[dict]:
    """Get progress for a pipeline run."""
    from backend.services.search_planner import get_pipeline_progress as _get
    return _get(run_id)


def get_all_pipelines() -> list[dict]:
    """Get all active pipeline runs."""
    from backend.services.search_planner import get_all_pipelines as _get
    return _get()


async def pipeline_event_stream(run_id: str):
    """SSE stream for pipeline progress."""
    from backend.services.search_planner import pipeline_event_stream as _stream
    async for event in _stream(run_id):
        yield event


class LeadDiscoveryPipeline:
    """Orchestrates the full lead discovery flow. Delegates to SearchPlanner."""

    def __init__(self):
        self.planner = _planner

    async def run(
        self,
        query: str,
        max_queries: int = 200,
        max_pages_per_spider: int = 3,
        sources: list[str] | None = None,
        max_concurrent: int = 4,
        skip_enrich: bool = False,
        skip_score: bool = False,
        skip_verify: bool = False,
    ) -> str:
        """Start the full lead discovery pipeline. Returns run_id."""
        return await self.planner.plan_and_execute(
            query=query,
            max_queries=max_queries,
            max_pages_per_spider=max_pages_per_spider,
            sources=sources,
            max_concurrent=max_concurrent,
            skip_enrich=skip_enrich,
            skip_score=skip_score,
            skip_verify=skip_verify,
        )
