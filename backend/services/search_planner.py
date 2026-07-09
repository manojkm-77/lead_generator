"""
BuyerHunter AI — AI Search Planner

Orchestrates the entire discovery flow:
1. Receives user query
2. Plans search strategy (which sources, how many queries, priority)
3. Expands queries via QueryExpander
4. Creates crawl jobs via CrawlJobQueue
5. Monitors progress and returns results
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from backend.services.query_expander import QueryExpander
from backend.services.crawl_queue import CrawlJobQueue
from backend.services.source_manager import get_source_registry, SourceRegistry, SpiderRunner

logger = logging.getLogger(__name__)


@dataclass
class SearchPlan:
    """The complete plan for a search discovery run."""
    run_id: str = ""
    query: str = ""
    query_type: str = "general"
    total_variations: int = 0
    total_jobs: int = 0
    sources_planned: dict = field(default_factory=dict)
    state_coverage: list = field(default_factory=list)
    estimated_jobs_per_source: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class PipelineProgress:
    """Live progress state for a pipeline run."""
    run_id: str
    status: str = "planning"
    query: str = ""
    query_type: str = "general"

    # Query expansion
    total_queries: int = 0
    completed_queries: int = 0

    # Crawling
    urls_found: int = 0
    pages_crawled: int = 0

    # Companies pipeline
    companies_found: int = 0
    companies_new: int = 0
    companies_duplicate: int = 0
    companies_merged: int = 0

    # Contacts
    emails_found: int = 0
    phones_found: int = 0
    whatsapp_found: int = 0
    websites_found: int = 0

    # Pipeline stages
    verified: int = 0
    enriched: int = 0
    scored: int = 0

    # Errors
    errors: int = 0

    # Current state
    current_source: str = ""
    current_query: str = ""
    active_jobs: int = 0
    queued_jobs: int = 0

    # Timing
    started_at: float = field(default_factory=time.time)
    elapsed: float = 0.0

    # Messages
    messages: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["elapsed"] = round(time.time() - self.started_at, 1)
        return d

    def add_message(self, msg: str):
        self.messages.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "message": msg,
        })
        logger.info(f"[Pipeline {self.run_id}] {msg}")


# ── Global progress store ─────────────────────────────────────────────────────
_progress_store: dict[str, PipelineProgress] = {}


def get_pipeline_progress(run_id: str) -> Optional[dict]:
    p = _progress_store.get(run_id)
    return p.to_dict() if p else None


def get_all_pipelines() -> list[dict]:
    return [p.to_dict() for p in _progress_store.values()]


async def pipeline_event_stream(run_id: str):
    """SSE generator for live pipeline progress."""
    last_msg_count = 0
    last_pages = 0
    last_companies = 0

    while True:
        progress = _progress_store.get(run_id)
        if not progress:
            break

        data = progress.to_dict()

        current_messages = len(progress.messages)
        changed = (
            current_messages > last_msg_count
            or progress.pages_crawled > last_pages
            or progress.companies_found > last_companies
            or progress.status in ("completed", "failed", "cancelled")
        )

        if changed:
            yield f"data: {json.dumps(data)}\n\n"
            last_msg_count = current_messages
            last_pages = progress.pages_crawled
            last_companies = progress.companies_found

        if progress.status in ("completed", "failed", "cancelled"):
            if current_messages > last_msg_count:
                yield f"data: {json.dumps(data)}\n\n"
            break

        await asyncio.sleep(0.5)


# ═══════════════════════════════════════════════════════════════════════════════
# Search Planner
# ═══════════════════════════════════════════════════════════════════════════════

class SearchPlanner:
    """Plans and orchestrates the entire search discovery flow."""

    def __init__(self):
        self.expander = QueryExpander()
        self.queue = CrawlJobQueue()
        self.sources = get_source_registry()
        self.spider_runner = SpiderRunner()

    async def plan_and_execute(
        self,
        query: str,
        max_queries: int = 500,
        max_pages_per_spider: int = 3,
        max_concurrent: int = 4,
        sources: list[str] | None = None,
        skip_enrich: bool = False,
        skip_score: bool = False,
        skip_verify: bool = False,
    ) -> str:
        """Plan the search and execute the full discovery pipeline. Returns run_id."""
        run_id = f"pip_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        progress = PipelineProgress(run_id=run_id, query=query)
        _progress_store[run_id] = progress

        async def _safe_execute():
            try:
                await self._execute_pipeline(
                    progress, query, max_queries, max_pages_per_spider,
                    max_concurrent, sources,
                    skip_enrich, skip_score, skip_verify,
                )
            except Exception as e:
                progress.status = "failed"
                progress.add_message(f"Pipeline crashed: {e}")
                logger.exception(f"Pipeline {run_id} crashed")

        import asyncio
        asyncio.create_task(_safe_execute())
        return run_id

    async def _execute_pipeline(
        self,
        progress: PipelineProgress,
        query: str,
        max_queries: int,
        max_pages_per_spider: int,
        max_concurrent: int,
        sources_filter: list[str] | None,
        skip_enrich: bool,
        skip_score: bool,
        skip_verify: bool,
    ):
        """Execute the full pipeline: plan → expand → queue → crawl → verify → enrich → score."""
        try:
            # ══════════════════════════════════════════════════════════════
            # STEP 1: Plan & Expand queries
            # ══════════════════════════════════════════════════════════════
            progress.status = "planning"
            plan = self._create_plan(query, max_queries)
            progress.query_type = plan.query_type
            progress.add_message(
                f"Planning search for '{query}' (type: {plan.query_type})"
            )

            progress.status = "expanding"
            variations = self.expander.expand(query, max_queries=max_queries)
            progress.total_queries = len(variations)
            progress.add_message(
                f"Generated {len(variations)} search variations across "
                f"{len(set(v['source'] for v in variations))} sources"
            )

            # Filter by sources if specified
            if sources_filter:
                variations = [v for v in variations if v["source"] in sources_filter]
                progress.total_queries = len(variations)
                progress.add_message(
                    f"Filtered to {len(variations)} queries for sources: {sources_filter}"
                )

            if not variations:
                progress.status = "failed"
                progress.add_message("No search variations generated. Check query.")
                return

            # ══════════════════════════════════════════════════════════════
            # STEP 2: Enqueue crawl jobs
            # ══════════════════════════════════════════════════════════════
            progress.status = "queuing"
            progress.add_message("Creating crawl jobs...")

            jobs = []
            for v in variations:
                jobs.append({
                    "query": v["query"],
                    "source": v["source"],
                    "priority": v.get("priority", 5),
                    "max_pages": max_pages_per_spider,
                    "intent": v.get("intent", ""),
                    "location": v.get("location", ""),
                })

            enqueued = self.queue.enqueue_batch(progress.run_id, jobs)
            progress.queued_jobs = enqueued
            progress.add_message(f"Enqueued {enqueued} crawl jobs in queue")

            # ══════════════════════════════════════════════════════════════
            # STEP 3: Execute crawl jobs in parallel
            # ══════════════════════════════════════════════════════════════
            progress.status = "crawling"
            progress.add_message(
                f"Starting parallel crawling with {max_concurrent} workers..."
            )

            await self._execute_crawl_jobs(progress, max_concurrent)

            # ══════════════════════════════════════════════════════════════
            # STEP 4: Deduplication
            # ══════════════════════════════════════════════════════════════
            progress.status = "deduplicating"
            progress.add_message("Running deduplication...")
            dedup_result = await self._run_deduplication(progress)
            progress.companies_new = dedup_result.get("new_count", 0)
            progress.companies_merged = dedup_result.get("merged_count", 0)
            progress.companies_duplicate = dedup_result.get("duplicate_count", 0)
            progress.add_message(
                f"Found {dedup_result.get('new_count', 0)} new, "
                f"{dedup_result.get('merged_count', 0)} merged, "
                f"{dedup_result.get('duplicate_count', 0)} duplicates"
            )

            # ══════════════════════════════════════════════════════════════
            # STEP 5: Verification
            # ══════════════════════════════════════════════════════════════
            if not skip_verify:
                progress.status = "verifying"
                progress.add_message("Cross-verifying company data...")
                verified = await self._verify_companies(progress)
                progress.verified = verified
                progress.add_message(f"Verified {verified} companies")

            # ══════════════════════════════════════════════════════════════
            # STEP 6: Website Enrichment
            # ══════════════════════════════════════════════════════════════
            if not skip_enrich:
                progress.status = "enriching"
                enriched = await self._enrich_companies(progress)
                progress.enriched = enriched
                progress.add_message(f"Enriched {enriched} company websites")

            # ══════════════════════════════════════════════════════════════
            # STEP 7: AI Scoring
            # ══════════════════════════════════════════════════════════════
            if not skip_score:
                progress.status = "scoring"
                scored = await self._score_companies(progress)
                progress.scored = scored
                progress.add_message(f"Scored {scored} companies")

            # ══════════════════════════════════════════════════════════════
            # DONE
            # ══════════════════════════════════════════════════════════════
            progress.status = "completed"

            # Get final stats from queue
            stats = self.queue.get_run_stats(progress.run_id)

            total_companies = progress.companies_new
            progress.add_message(
                f"Pipeline complete! "
                f"Queries: {stats.get('completed', 0)}/{stats.get('total', 0)} | "
                f"Companies: {total_companies} (+{progress.companies_merged} merged) | "
                f"Emails: {progress.emails_found} | Phones: {progress.phones_found} | "
                f"Websites: {progress.websites_found}"
            )
            progress.add_message(f"Total time: {progress.elapsed:.1f}s")

        except Exception as e:
            progress.status = "failed"
            progress.add_message(f"Pipeline failed: {e}")
            logger.exception(f"Pipeline {progress.run_id} failed")

    def _create_plan(self, query: str, max_queries: int) -> SearchPlan:
        """Create a search plan without executing."""
        query_type = self.expander._detect_query_type(query)
        return SearchPlan(
            run_id=f"plan_{int(time.time())}",
            query=query,
            query_type=query_type,
        )

    async def _execute_crawl_jobs(self, progress: PipelineProgress, max_concurrent: int):
        """Execute crawl jobs in parallel using worker tasks."""
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)
        active_tasks = []
        _cancelled = False

        async def _worker():
            nonlocal _cancelled
            while not _cancelled:
                jobs = self.queue.dequeue(progress.run_id, limit=1)
                if not jobs:
                    break

                job = jobs[0]
                job_id = job.id
                query = job.query
                source = job.source
                max_pages = job.max_pages

                progress.current_query = query
                progress.current_source = source
                progress.active_jobs += 1

                progress.add_message(
                    f"[{progress.completed_queries + 1}/{progress.total_queries}] "
                    f"Crawling '{query}' on {source}"
                )

                try:
                    async with semaphore:
                        result = await self.spider_runner.run_spider(
                            source, query, max_pages
                        )

                        progress.completed_queries += 1
                        progress.pages_crawled += result.pages_crawled

                        if result.success:
                            self.queue.complete(
                                job_id,
                                companies_found=len(result.companies),
                                pages_crawled=result.pages_crawled,
                            )

                            new_count = len(result.companies)
                            progress.companies_found += new_count
                            progress.urls_found += len(result.urls_visited)

                            for c in result.companies:
                                if c.email:
                                    progress.emails_found += 1
                                if c.phone:
                                    progress.phones_found += 1
                                if c.whatsapp_business:
                                    progress.whatsapp_found += 1
                                if c.website:
                                    progress.websites_found += 1

                            logger.info(
                                f"[Pipeline] {source} '{query}': {new_count} companies"
                            )
                        else:
                            self.queue.fail(job_id, "; ".join(result.errors))
                            progress.errors += 1
                            logger.warning(
                                f"[Pipeline] {source} '{query}' failed: {result.errors}"
                            )

                except asyncio.CancelledError:
                    _cancelled = True
                    self.queue.fail(job_id, "Worker cancelled")
                except Exception as e:
                    progress.errors += 1
                    self.queue.fail(job_id, str(e))
                    logger.error(f"[Pipeline] Error on '{query}': {e}")
                finally:
                    progress.active_jobs -= 1

        # Launch N concurrent workers
        import asyncio
        for _ in range(max_concurrent):
            task = asyncio.create_task(_worker())
            active_tasks.append(task)

        await asyncio.gather(*active_tasks, return_exceptions=True)

        # Update final stats from queue
        stats = self.queue.get_run_stats(progress.run_id)
        progress.completed_queries = stats.get("completed", 0)
        progress.errors = stats.get("failed", 0)

    async def _run_deduplication(self, progress: PipelineProgress) -> dict:
        """Run deduplication on companies discovered in this run."""
        from backend.services.deduplication import DeduplicationEngine

        def _dedup():
            dedup = DeduplicationEngine()
            # Get newly discovered companies (from latest crawl run)
            import sqlite3
            conn = sqlite3.connect("buyerhunter.db")
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """SELECT * FROM companies
                ORDER BY id DESC
                LIMIT 500"""
            ).fetchall()

            companies = [dict(r) for r in rows]
            conn.close()

            result = dedup.deduplicate_batch(companies)
            return result

        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, _dedup)

    async def _verify_companies(self, progress: PipelineProgress) -> int:
        """Verify recently added companies."""
        from backend.services.verification import VerificationEngine

        def _verify():
            verifier = VerificationEngine()
            result = verifier.batch_verify(limit=100)
            return result.get("verified", 0)

        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, _verify)

    async def _enrich_companies(self, progress: PipelineProgress) -> int:
        """Enrich companies that have websites."""
        from backend.services.enrichment import EnrichmentService

        try:
            service = EnrichmentService()
            result = await service.enrich_batch(limit=20)
            return result.get("enriched", 0)
        except Exception as e:
            logger.error(f"Enrichment error: {e}")
            return 0

    async def _score_companies(self, progress: PipelineProgress) -> int:
        """Score unscored companies."""
        def _score():
            import sqlite3
            conn = sqlite3.connect("buyerhunter.db")
            conn.row_factory = sqlite3.Row

            try:
                unscored = conn.execute(
                    "SELECT COUNT(*) FROM companies WHERE lead_score = 0 AND confidence = 0"
                ).fetchone()[0]
            except sqlite3.OperationalError:
                unscored = conn.execute(
                    "SELECT COUNT(*) FROM companies WHERE lead_score = 0"
                ).fetchone()[0]
            if unscored == 0:
                conn.close()
                return 0

            batch_size = min(unscored, 50)
            rows = conn.execute(
                "SELECT * FROM companies WHERE lead_score = 0 LIMIT ?", (batch_size,)
            ).fetchall()

            scored = 0
            for row in rows:
                company = dict(row)
                score_data = self._quick_score(company)
                try:
                    conn.execute(
                        "UPDATE companies SET lead_score = ?, confidence = ? WHERE id = ?",
                        (score_data["score"], score_data["confidence"], row["id"]),
                    )
                except sqlite3.OperationalError:
                    conn.execute(
                        "UPDATE companies SET lead_score = ? WHERE id = ?",
                        (score_data["score"], row["id"]),
                    )
                scored += 1

            conn.commit()
            conn.close()
            return scored

        import asyncio
        return await asyncio.get_event_loop().run_in_executor(None, _score)

    def _quick_score(self, company: dict) -> dict:
        """Quick heuristic scoring (no AI call needed)."""
        score = 0
        confidence = 30

        if company.get("website"):
            score += 15
            confidence += 10
        if company.get("email"):
            score += 15
            confidence += 10
        if company.get("phone"):
            score += 10
            confidence += 5
        if company.get("gst_number"):
            score += 10
            confidence += 15
        if company.get("official_email"):
            score += 5

        industry = (company.get("industry") or "").lower()
        oil_keywords = ["edible oil", "oil", "food", "bakery", "snack", "soap",
                        "vanaspati", "palm oil", "vegetable oil", "cooking oil"]
        if any(kw in industry for kw in oil_keywords):
            score += 25
            confidence += 10
        elif "restaurant" in industry or "hotel" in industry:
            score += 20
            confidence += 5

        if company.get("is_manufacturer"):
            score += 10
        if company.get("is_importer"):
            score += 10
        if company.get("is_distributor"):
            score += 5

        if company.get("products"):
            score += 5

        return {
            "score": min(score, 100),
            "confidence": min(confidence, 100),
        }

    async def preview_expansion(self, query: str, max_queries: int = 500) -> dict:
        """Preview query expansion without executing crawls."""
        variations = self.expander.expand(query, max_queries=max_queries)

        by_source = {}
        for v in variations:
            src = v["source"]
            by_source[src] = by_source.get(src, 0) + 1

        return {
            "query": query,
            "query_type": self.expander._detect_query_type(query),
            "total_variations": len(variations),
            "by_source": by_source,
            "by_type": {},
            "locations_covered": len(set(v.get("location", "India") for v in variations)),
            "variations": variations[:100],
        }
