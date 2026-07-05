"""
BuyerHunter AI — Crawl Job Queue

SQLite-backed job queue for managing crawl operations.
Supports prioritization, retry, rate limiting, and status tracking.
"""

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = "buyerhunter.db"


def _init_queue_db():
    """Create crawl_jobs table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS crawl_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            query TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            priority INTEGER DEFAULT 5,
            max_pages INTEGER DEFAULT 3,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 2,
            companies_found INTEGER DEFAULT 0,
            pages_crawled INTEGER DEFAULT 0,
            error_message TEXT,
            created_at REAL NOT NULL,
            started_at REAL,
            completed_at REAL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_jobs_run_id ON crawl_jobs(run_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_crawl_jobs_status ON crawl_jobs(status)
    """)
    conn.commit()
    conn.close()


# Initialize on import
_init_queue_db()


@dataclass
class CrawlJob:
    id: int = 0
    run_id: str = ""
    query: str = ""
    source: str = ""
    status: str = "queued"
    priority: int = 5
    max_pages: int = 3
    retry_count: int = 0
    max_retries: int = 2
    companies_found: int = 0
    pages_crawled: int = 0
    error_message: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self):
        return asdict(self)


class CrawlJobQueue:
    """Manages crawl jobs with SQLite backing."""

    def __init__(self):
        pass

    def enqueue_batch(self, run_id: str, jobs: list[dict]) -> int:
        """
        Enqueue a batch of crawl jobs.

        Each job dict should have: query, source, priority (optional), max_pages (optional)
        Returns number of jobs enqueued.
        """
        conn = sqlite3.connect(DB_PATH)
        now = time.time()
        count = 0

        for job in jobs:
            try:
                conn.execute(
                    """INSERT INTO crawl_jobs
                    (run_id, query, source, status, priority, max_pages, created_at)
                    VALUES (?, ?, ?, 'queued', ?, ?, ?)""",
                    (
                        run_id,
                        job["query"],
                        job["source"],
                        job.get("priority", 5),
                        job.get("max_pages", 3),
                        now,
                    ),
                )
                count += 1
            except Exception as e:
                logger.error(f"Failed to enqueue job: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Enqueued {count} crawl jobs for run {run_id}")
        return count

    def dequeue(self, run_id: str, limit: int = 1) -> list[CrawlJob]:
        """
        Get the next batch of queued jobs, ordered by priority.
        Marks them as 'running' atomically.
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        # Get queued jobs
        rows = conn.execute(
            """SELECT * FROM crawl_jobs
            WHERE run_id = ? AND status = 'queued'
            ORDER BY priority DESC, created_at ASC
            LIMIT ?""",
            (run_id, limit),
        ).fetchall()

        jobs = []
        now = time.time()

        for row in rows:
            # Atomically mark as running
            cursor = conn.execute(
                """UPDATE crawl_jobs SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'queued'""",
                (now, row["id"]),
            )
            if cursor.rowcount > 0:
                jobs.append(CrawlJob(**dict(row)))

        conn.commit()
        conn.close()
        return jobs

    def complete(self, job_id: int, companies_found: int = 0, pages_crawled: int = 0):
        """Mark a job as completed."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """UPDATE crawl_jobs SET status = 'completed', companies_found = ?,
            pages_crawled = ?, completed_at = ?
            WHERE id = ?""",
            (companies_found, pages_crawled, time.time(), job_id),
        )
        conn.commit()
        conn.close()

    def fail(self, job_id: int, error: str = ""):
        """Mark a job as failed. Retry if under max_retries."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT retry_count, max_retries FROM crawl_jobs WHERE id = ?",
            (job_id,),
        ).fetchone()

        if row and row["retry_count"] < row["max_retries"]:
            # Requeue for retry
            conn.execute(
                """UPDATE crawl_jobs SET status = 'queued',
                retry_count = retry_count + 1, error_message = ?
                WHERE id = ?""",
                (error, job_id),
            )
            logger.info(f"Job {job_id} requeued for retry (attempt {row['retry_count'] + 1})")
        else:
            conn.execute(
                """UPDATE crawl_jobs SET status = 'failed', error_message = ?,
                completed_at = ?
                WHERE id = ?""",
                (error, time.time(), job_id),
            )
            logger.warning(f"Job {job_id} failed permanently: {error}")

        conn.commit()
        conn.close()

    def get_run_stats(self, run_id: str) -> dict:
        """Get aggregate stats for a pipeline run."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'queued' THEN 1 ELSE 0 END) as queued,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(companies_found) as companies_found,
                SUM(pages_crawled) as pages_crawled
            FROM crawl_jobs WHERE run_id = ?""",
            (run_id,),
        ).fetchone()

        conn.close()
        return dict(row) if row else {
            "total": 0, "queued": 0, "running": 0,
            "completed": 0, "failed": 0,
            "companies_found": 0, "pages_crawled": 0,
        }

    def get_run_jobs(self, run_id: str) -> list[dict]:
        """Get all jobs for a run."""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM crawl_jobs WHERE run_id = ? ORDER BY priority DESC, created_at ASC",
            (run_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def cancel_run(self, run_id: str):
        """Cancel all queued/running jobs for a run."""
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """UPDATE crawl_jobs SET status = 'cancelled'
            WHERE run_id = ? AND status IN ('queued', 'running')""",
            (run_id,),
        )
        conn.commit()
        conn.close()
