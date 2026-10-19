from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_admin_user
from app.models.models import User, JobListing, Skill
from app.schemas.schemas import ScrapeResponse, ScrapeRequest, AdminStatsResponse
from app.services.scraper import scrape_and_ingest_telegram

router = APIRouter(prefix="/admin", tags=["Admin & Data Scraping"])

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Get system-wide overview statistics.
    Admin privileges required.
    """
    total_candidates = db.query(User).filter(User.role == "user").count()
    total_jobs = db.query(JobListing).count()
    total_skills = db.query(Skill).count()

    import re
    sources = [s[0] for s in db.query(JobListing.source).distinct().all()]

    # Count jobs per source (JobNet, BongThom, Khmer24, Telegram, etc.)
    jobs_by_source = {}
    for s in sources:
        jobs_by_source[s] = db.query(JobListing).filter(JobListing.source == s).count()

    # Extract distinct Telegram channel names from stored source_urls
    tg_jobs = db.query(JobListing.source_url).filter(JobListing.source == "Telegram").all()
    telegram_channels = set()
    for row in tg_jobs:
        url = row[0] or ""
        match = re.search(r't\.me/(?:s/)?([^/]+)', url)
        if match:
            telegram_channels.add(f"@{match.group(1)}")

    from app.services.scheduler import get_scheduler_status
    sched = get_scheduler_status()

    return AdminStatsResponse(
        total_candidates=total_candidates,
        total_jobs=total_jobs,
        total_skills=total_skills,
        active_sources=sources,
        jobs_by_source=jobs_by_source,
        telegram_channels=sorted(list(telegram_channels)),
        auto_scraper_status=sched["current_status"],
        last_scraped_at=sched["last_scraped_at"],
        next_scrape_in_minutes=60
    )

from app.services.importer import import_from_json_file
import os

@router.post("/scrape", response_model=ScrapeResponse, status_code=status.HTTP_200_OK)
def trigger_scrape(
    request: ScrapeRequest = ScrapeRequest(),
    admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    EP-13: Trigger data ingestion from specified sources (Telegram or Web Aggregators).
    Admin privileges required (returns 403 Forbidden for regular users).
    Supports: 'all', 'telegram', 'khmer24', 'bongthom', 'jobnet', 'cambojob', etc.
    """
    src_lower = request.source.lower().strip()
    poc_dir = "/Users/microstore/Documents/RUPP_YEAR_4/PP/POC"

    # Map friendly source names or URLs to datasets
    source_files = {
        "khmer24": "Khmer24_com.json",
        "bongthom": "BongThom_com.json",
        "jobnet": "JobNet_com_kh.json",
        "cambojob": "cambojob_com.json",
        "workingna": "workingna_com.json",
        "aseanworks": "AseanWorks_com.json",
        "forval": "forval_com.json",
        "pphr": "pphr_com.json",
        "all": "jobs_all.json",
    }

    # Resolve matched source key from either name or URL
    matched_key = None
    for key in source_files:
        if key in src_lower:
            matched_key = key
            break

    if matched_key and os.path.exists(os.path.join(poc_dir, source_files[matched_key])):
        filepath = os.path.join(poc_dir, source_files[matched_key])
        res = import_from_json_file(db, filepath, dry_run=request.dry_run)
        total_jobs = db.query(JobListing).count()
        return ScrapeResponse(
            status="completed" if not request.dry_run else "dry_run",
            source=matched_key.capitalize(),
            new_jobs_added=res["inserted"],
            duplicates_skipped=res["updated"],
            total_jobs=total_jobs,
            channel=None
        )

    # Otherwise default to Telegram live scraping
    tg_result = scrape_and_ingest_telegram(db=db, channel_or_url=request.source)
    return ScrapeResponse(
        status=tg_result.get("status", "success"),
        source="Telegram",
        new_jobs_added=tg_result.get("new_jobs_added", 0),
        duplicates_skipped=0,
        total_jobs=tg_result.get("total_jobs", db.query(JobListing).count()),
        channel=tg_result.get("channel")
    )
