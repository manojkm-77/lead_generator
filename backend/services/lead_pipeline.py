"""
BuyerHunter AI — Lead Discovery Pipeline

End-to-end pipeline: Search → Discover → Verify → Enrich → Score → Save
With live progress tracking via SSE.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

from backend.services.query_expander import QueryExpander
from backend.services.spider_manager import SpiderManager

logger = logging.getLogger(__name__)


@dataclass
class PipelineProgress:
    """Live progress state for a pipeline run."""
    run_id: str
    status: str = "starting"  # starting, searching, crawling, enriching, scoring, completed, failed
    query: str = ""
    total_queries: int = 0
    completed_queries: int = 0
    companies_found: int = 0
    companies_new: int = 0
    companies_duplicate: int = 0
    emails_found: int = 0
    phones_found: int = 0
    whatsapp_found: int = 0
    websites_found: int = 0
    verified: int = 0
    enriched: int = 0
    scored: int = 0
    errors: int = 0
    current_source: str = ""
    current_query: str = ""
    started_at: float = field(default_factory=time.time)
    elapsed: float = 0.0
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


# ── Global progress store (in-memory for SSE) ────────────────────────────────
_progress_store: dict[str, PipelineProgress] = {}


def get_pipeline_progress(run_id: str) -> Optional[dict]:
    p = _progress_store.get(run_id)
    return p.to_dict() if p else None


def get_all_pipelines() -> list[dict]:
    return [p.to_dict() for p in _progress_store.values()]


async def pipeline_event_stream(run_id: str):
    """SSE generator for live pipeline progress."""
    import json as _json
    last_len = 0
    while True:
        progress = _progress_store.get(run_id)
        if not progress:
            break
        data = progress.to_dict()
        # Only send if there's new data
        current_len = len(progress.messages)
        if current_len > last_len:
            yield f"data: {_json.dumps(data)}\n\n"
            last_len = current_len
        if progress.status in ("completed", "failed"):
            yield f"data: {_json.dumps(data)}\n\n"
            break
        await asyncio.sleep(1.0)


class LeadDiscoveryPipeline:
    """Orchestrates the full lead discovery flow."""

    def __init__(self):
        self.expander = QueryExpander()
        self.spider_manager = SpiderManager()

    async def run(
        self,
        query: str,
        max_queries: int = 50,
        max_pages_per_spider: int = 3,
        sources: list[str] | None = None,
        skip_enrich: bool = False,
        skip_score: bool = False,
    ) -> str:
        """
        Start the full lead discovery pipeline.

        Returns a run_id for tracking progress via SSE.
        """
        run_id = f"pipeline_{int(time.time())}"
        progress = PipelineProgress(run_id=run_id, query=query)
        _progress_store[run_id] = progress

        async def _safe_run():
            try:
                await self._execute_pipeline(progress, query, max_queries,
                                             max_pages_per_spider, sources,
                                             skip_enrich, skip_score)
            except Exception as e:
                progress.status = "failed"
                progress.add_message(f"Pipeline crashed: {e}")
                logger.exception(f"Pipeline {run_id} crashed")

        asyncio.create_task(_safe_run())

        return run_id

    async def _execute_pipeline(
        self,
        progress: PipelineProgress,
        query: str,
        max_queries: int,
        max_pages_per_spider: int,
        sources: list[str] | None,
        skip_enrich: bool,
        skip_score: bool,
    ):
        try:
            # ── STEP 1: Expand queries ────────────────────────────────────
            progress.status = "searching"
            progress.add_message(f"Expanding search query: {query}")

            variations = self.expander.expand(query, max_queries=max_queries)
            progress.total_queries = len(variations)
            progress.add_message(f"Generated {len(variations)} search variations")

            # Filter by sources if specified
            if sources:
                variations = [v for v in variations if v["source"] in sources]
                progress.total_queries = len(variations)
                progress.add_message(f"Filtered to {len(variations)} queries for sources: {sources}")

            # ── STEP 2: Crawl each variation ─────────────────────────────
            progress.status = "crawling"
            all_companies = []

            for i, variation in enumerate(variations):
                progress.current_query = variation["query"]
                progress.current_source = variation["source"]
                progress.completed_queries = i

                progress.add_message(
                    f"[{i+1}/{len(variations)}] Crawling '{variation['query']}' "
                    f"on {variation['source']}"
                )

                try:
                    companies = await self._crawl_variation(
                        variation, max_pages_per_spider
                    )
                    all_companies.extend(companies)

                    # Count contacts
                    for c in companies:
                        if c.get("email"):
                            progress.emails_found += 1
                        if c.get("phone"):
                            progress.phones_found += 1
                        if c.get("whatsapp"):
                            progress.whatsapp_found += 1
                        if c.get("website"):
                            progress.websites_found += 1

                    progress.companies_found = len(all_companies)

                except Exception as e:
                    progress.errors += 1
                    progress.add_message(f"Error crawling: {e}")

                # Rate limit between queries
                await asyncio.sleep(1.0)

            progress.completed_queries = len(variations)
            progress.add_message(
                f"Crawling complete. Found {len(all_companies)} total results"
            )

            # ── STEP 3: Deduplicate & Save ───────────────────────────────
            progress.status = "saving"
            saved_count = await self._save_companies(all_companies, progress)
            progress.add_message(f"Saved {saved_count} unique companies")

            # ── STEP 4: Enrich ────────────────────────────────────────────
            if not skip_enrich:
                progress.status = "enriching"
                enriched = await self._enrich_new_companies(progress)
                progress.enriched = enriched
                progress.add_message(f"Enriched {enriched} companies")

            # ── STEP 5: Score ─────────────────────────────────────────────
            if not skip_score:
                progress.status = "scoring"
                scored = await self._score_companies(progress)
                progress.scored = scored
                progress.add_message(f"Scored {scored} companies")

            # ── DONE ──────────────────────────────────────────────────────
            progress.status = "completed"
            progress.add_message(
                f"Pipeline complete! {saved_count} companies added, "
                f"{progress.emails_found} emails, {progress.phones_found} phones"
            )

        except Exception as e:
            progress.status = "failed"
            progress.add_message(f"Pipeline failed: {e}")
            logger.exception(f"Pipeline {progress.run_id} failed")

    async def _crawl_variation(self, variation: dict, max_pages: int) -> list[dict]:
        """Crawl a single search variation using the appropriate spider."""
        spider_name = variation["source"]

        if spider_name not in SpiderManager.SPIDER_REGISTRY:
            logger.warning(f"Unknown spider: {spider_name}, skipping")
            return []

        try:
            before_count = await self._get_company_count()
            logger.info(f"[Pipeline] Before={before_count}, spider={spider_name}, query={variation['query']}")
            result = await self.spider_manager.run_spider(
                spider_name,
                queries=[variation["query"]],
                max_pages=max_pages,
            )

            # Wait for subprocess SQLite writes to flush to disk
            for attempt in range(5):
                await asyncio.sleep(1)
                after_count = await self._get_company_count()
                if after_count > before_count:
                    break

            logger.info(f"[Pipeline] After={after_count}, status={result.get('status')}, RC={result.get('return_code')}, new={after_count - before_count}")
            if result.get("stderr"):
                logger.info(f"[Pipeline] stderr={result['stderr'][-300:]}")

            new_count = after_count - before_count
            if new_count > 0:
                return await self._get_recent_companies(new_count)
            elif result.get("status") != "completed":
                logger.warning(f"[Pipeline] Crawl failed: {result.get('stderr', '')[-200:]}")

            return []

        except asyncio.TimeoutError:
            logger.warning(f"Crawl timeout for {variation['query']}")
            return []
        except Exception as e:
            logger.error(f"Crawl error for {variation['query']}: {e}")
            return []

    async def _direct_search(self, query: str) -> list[dict]:
        """Use httpx to search IndiaMART directly."""
        from backend.services.direct_search import DirectSearch
        search = DirectSearch()
        try:
            companies = await search.search_indiamart(query, max_results=20)
            logger.info(f"Direct search for '{query}': found {len(companies)} companies")
            return companies
        finally:
            await search.close()

    async def _get_company_count(self) -> int:
        """Get current total company count via raw sqlite3 (reads uncommitted subprocess writes)."""
        import sqlite3
        def _count():
            conn = sqlite3.connect("buyerhunter.db")
            count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
            conn.close()
            return count
        return await asyncio.get_event_loop().run_in_executor(None, _count)

    async def _get_recent_companies(self, count: int) -> list[dict]:
        """Get the most recently added companies via raw sqlite3."""
        import sqlite3
        def _fetch():
            conn = sqlite3.connect("buyerhunter.db")
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM companies ORDER BY id DESC LIMIT ?", (count,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        rows = await asyncio.get_event_loop().run_in_executor(None, _fetch)
        # Map snake_case keys to match model fields
        companies = []
        for r in rows:
            companies.append({
                "company_name": r.get("company_name"),
                "website": r.get("website"),
                "phone": r.get("phone"),
                "whatsapp": r.get("whatsapp"),
                "email": r.get("email"),
                "address": r.get("address"),
                "city": r.get("city"),
                "state": r.get("state"),
                "industry": r.get("industry"),
                "products": r.get("products"),
                "source": r.get("source"),
                "gst_number": r.get("gst_number"),
                "is_manufacturer": r.get("is_manufacturer"),
                "is_importer": r.get("is_importer"),
                "is_exporter": r.get("is_exporter"),
            })
        return companies

    async def _save_companies(
        self, companies: list[dict], progress: PipelineProgress
    ) -> int:
        """Deduplicate and save companies via raw sqlite3 (consistent with subprocess writes)."""
        import sqlite3

        def _save():
            conn = sqlite3.connect("buyerhunter.db")
            conn.row_factory = sqlite3.Row
            saved = 0
            for company_data in companies:
                try:
                    name = (company_data.get("company_name") or "").strip()
                    if not name:
                        continue
                    phone = company_data.get("phone") or ""

                    # Dedup by name+phone
                    existing = conn.execute(
                        "SELECT id FROM companies WHERE LOWER(company_name) = ? AND (phone = ? OR (phone IS NULL AND ? = ''))",
                        (name.lower(), phone, phone),
                    ).fetchone()

                    if existing:
                        progress.companies_duplicate += 1
                        continue

                    conn.execute(
                        """INSERT INTO companies
                        (company_name, website, phone, whatsapp, email, address,
                         city, state, country, gst_number, industry, products,
                         lead_score, source, crawl_date, is_manufacturer, is_importer, is_exporter)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            name,
                            company_data.get("website"),
                            company_data.get("phone"),
                            company_data.get("whatsapp"),
                            company_data.get("email"),
                            company_data.get("address"),
                            company_data.get("city"),
                            company_data.get("state"),
                            company_data.get("country", "India"),
                            company_data.get("gst_number"),
                            company_data.get("industry"),
                            company_data.get("products"),
                            company_data.get("lead_score", 0),
                            company_data.get("source", "pipeline"),
                            company_data.get("crawl_date"),
                            company_data.get("is_manufacturer", False),
                            company_data.get("is_importer", False),
                            company_data.get("is_exporter", False),
                        ),
                    )
                    saved += 1
                    progress.companies_new += 1
                except Exception as e:
                    progress.errors += 1
                    logger.error(f"Error saving company: {e}")

            conn.commit()
            conn.close()
            return saved

        return await asyncio.get_event_loop().run_in_executor(None, _save)

    async def _enrich_new_companies(self, progress: PipelineProgress) -> int:
        """Enrich companies that have websites but haven't been enriched."""
        import sqlite3

        def _count_pending():
            conn = sqlite3.connect("buyerhunter.db")
            count = conn.execute(
                "SELECT COUNT(*) FROM companies WHERE website IS NOT NULL AND website != '' AND enriched_at IS NULL"
            ).fetchone()[0]
            conn.close()
            return count

        pending = await asyncio.get_event_loop().run_in_executor(None, _count_pending)
        if pending == 0:
            return 0

        from backend.services.enrichment import EnrichmentService
        service = EnrichmentService()
        batch_size = min(pending, 20)
        result = await service.enrich_batch(limit=batch_size)
        return result.get("enriched", 0)

    async def _score_companies(self, progress: PipelineProgress) -> int:
        """Score unscored companies via raw sqlite3."""
        import sqlite3

        def _score():
            conn = sqlite3.connect("buyerhunter.db")
            conn.row_factory = sqlite3.Row
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
                try:
                    score_data = self._quick_score(dict(row))
                    conn.execute(
                        "UPDATE companies SET lead_score = ?, confidence = ? WHERE id = ?",
                        (score_data["score"], score_data["confidence"], row["id"]),
                    )
                    scored += 1
                except Exception as e:
                    logger.error(f"Scoring error: {e}")

            conn.commit()
            conn.close()
            return scored

        return await asyncio.get_event_loop().run_in_executor(None, _score)

    def _quick_score(self, company: dict) -> dict:
        """Quick heuristic scoring (no AI call needed)."""
        score = 0
        confidence = 50

        # Has website = more legitimate
        if company.get("website"):
            score += 15
            confidence += 10

        # Has email = reachable
        if company.get("email"):
            score += 15
            confidence += 10

        # Has phone = reachable
        if company.get("phone"):
            score += 10
            confidence += 5

        # Has GST = verified business
        if company.get("gst_number"):
            score += 10
            confidence += 15

        # Industry relevance
        industry = (company.get("industry") or "").lower()
        if any(kw in industry for kw in ["edible oil", "oil", "food", "bakery", "snack", "soap", "vanaspati"]):
            score += 25
            confidence += 10

        # Business type
        if company.get("is_manufacturer"):
            score += 10
        if company.get("is_importer"):
            score += 10
        if company.get("is_distributor"):
            score += 5

        # Location (Gujarat/Maharashtra are key edible oil hubs)
        state = (company.get("state") or "").lower()
        if state in ["gujarat", "maharashtra", "tamil nadu", "karnataka", "west bengal"]:
            score += 5

        # Has products listed
        if company.get("products"):
            score += 5

        return {
            "score": min(score, 100),
            "confidence": min(confidence, 100),
        }
