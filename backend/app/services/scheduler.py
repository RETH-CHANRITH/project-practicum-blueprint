"""
backend/app/services/scheduler.py
=================================
Automated Background Scraping Worker for JobMatch.

Periodically syncs Telegram channels and external job sources on a configurable interval.
Provides live status tracking (idle, running, last_scraped_at) for the Admin UI.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.scraper import scrape_and_ingest_telegram

logger = logging.getLogger(__name__)

# State tracker for UI display
scheduler_state: Dict[str, Any] = {
    "is_running": False,
    "current_status": "active",  # 'active', 'scraping_in_progress', 'idle'
    "last_scraped_at": None,
    "last_run_jobs_added": 0,
    "last_error": None,
}

async def auto_scrape_loop():
    """Background task that runs continuously while the FastAPI server is alive."""
    logger.info(
        "Auto-scraper background task initiated. Interval: %s minutes",
        settings.SCRAPER_INTERVAL_MINUTES
    )
    
    # Optional short delay on boot to allow DB connection pool to settle
    await asyncio.sleep(5)

    while True:
        try:
            scheduler_state["current_status"] = "scraping_in_progress"
            logger.info("Executing scheduled job scraping cycle...")

            # Run in worker thread so it doesn't block FastAPI async event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, _execute_scrape_sync)

            scheduler_state["last_scraped_at"] = datetime.utcnow().isoformat() + "Z"
            scheduler_state["last_run_jobs_added"] = result.get("new_jobs_added", 0)
            scheduler_state["current_status"] = "active"
            scheduler_state["last_error"] = None

            logger.info("Auto-scrape cycle completed: %s", result)

        except Exception as exc:
            logger.error("Auto-scrape cycle failed: %s", exc)
            scheduler_state["current_status"] = "idle"
            scheduler_state["last_error"] = str(exc)

        # Sleep for configured interval
        interval_seconds = max(60, settings.SCRAPER_INTERVAL_MINUTES * 60)
        await asyncio.sleep(interval_seconds)


def _execute_scrape_sync() -> Dict[str, Any]:
    """
    Synchronous scrape execution.
    Automatically queries all active Telegram channels stored in the database
    and scrapes every one of them on each cycle.
    """
    import re
    from app.models.models import JobListing

    db = SessionLocal()
    total_new_added = 0
    scraped_channels = set(["internshipscambodia"])

    try:
        # Find all Telegram channels previously ingested into the system
        tg_jobs = db.query(JobListing.source_url).filter(JobListing.source == "Telegram").all()
        for row in tg_jobs:
            url = row[0] or ""
            match = re.search(r't\.me/(?:s/)?([^/]+)', url)
            if match:
                scraped_channels.add(match.group(1).lstrip("@"))

        # Scrape each active channel automatically
        for ch in scraped_channels:
            try:
                res = scrape_and_ingest_telegram(db=db, channel_or_url=ch)
                total_new_added += res.get("new_jobs_added", 0)
            except Exception as e:
                logger.warning("Auto-scrape for channel @%s encountered error: %s", ch, e)

        return {
            "status": "success",
            "channels_scraped": [f"@{c}" for c in sorted(scraped_channels)],
            "new_jobs_added": total_new_added
        }
    finally:
        db.close()


def get_scheduler_status() -> Dict[str, Any]:
    """Returns current scheduler state for the Admin API/UI."""
    return scheduler_state
