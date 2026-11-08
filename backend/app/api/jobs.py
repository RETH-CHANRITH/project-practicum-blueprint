from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.database import get_db
from app.models.models import JobListing, Skill, JobSkill
from app.schemas.schemas import (
    JobListResponse, JobItemResponse, JobDetailResponse,
    JobIngestRequest, JobIngestResponse
)
from app.services.dedup_manager import save_job_with_dedup
from app.services.job_classifier import classify_job

router = APIRouter(prefix="/jobs", tags=["Job Discovery"])

def format_job_item(job: JobListing) -> JobItemResponse:
    skill_names = [js.skill.name for js in job.skills if js.skill]
    return JobItemResponse(
        id=job.id,
        source_id=job.source_id,
        title=job.title,
        company=job.company,
        location=job.location,
        experience_level=job.experience_level,
        job_type=job.job_type,
        salary_min=float(job.salary_min) if job.salary_min is not None else None,
        salary_max=float(job.salary_max) if job.salary_max is not None else None,
        salary_currency=job.salary_currency,
        is_negotiable=job.is_negotiable,
        work_arrangement=job.work_arrangement,
        job_category=job.job_category,
        job_subcategory=job.job_subcategory,
        job_level=job.job_level,
        classification_confidence=job.classification_confidence,
        classification_source=job.classification_source,
        company_logo_url=job.company_logo_url,
        company_url=job.company_url,
        application_url=job.application_url,
        status=job.status,
        source=job.source,
        source_url=job.source_url,
        posted_at=str(job.posted_at) if job.posted_at else None,
        deadline=str(job.deadline) if job.deadline else None,
        skills=skill_names
    )

@router.get("", response_model=JobListResponse)
def list_jobs(
    search: Optional[str] = Query(None, description="Search keyword in title, company, or description"),
    source: Optional[str] = Query(None, description="Filter by source name/portal"),
    source_id: Optional[int] = Query(None, description="Filter by master source ID"),
    experience_level: Optional[str] = Query(None, description="Filter: entry, junior, mid, senior"),
    job_category: Optional[str] = Query(None, description="Filter by job category (e.g. Information Technology)"),
    location: Optional[str] = Query(None, description="Filter by location (e.g. Phnom Penh)"),
    min_salary: Optional[float] = Query(None, description="Minimum expected salary"),
    since: Optional[str] = Query(None, description="Filter jobs created/seen since timestamp (ISO 8601 or YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """EP-07: Search and filter aggregated jobs with pagination (returns unique main jobs only)"""
    query = db.query(JobListing).filter(
        JobListing.is_active == True,
        JobListing.duplicate_of.is_(None)
    )

    if since:
        try:
            clean_since = since.strip().replace(" ", "+").replace("Z", "+00:00")
            since_dt = datetime.fromisoformat(clean_since)
            query = query.filter(JobListing.created_at >= since_dt)
        except Exception:
            pass

    if source_id is not None:
        query = query.filter(JobListing.source_id == source_id)

    if source:
        query = query.filter(JobListing.source.ilike(f"%{source.strip()}%"))

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                JobListing.title.ilike(term),
                JobListing.company.ilike(term),
                JobListing.description.ilike(term),
                JobListing.skills.any(JobSkill.skill.has(Skill.name.ilike(term)))
            )
        )

    if experience_level:
        query = query.filter(JobListing.experience_level == experience_level.strip().lower())

    if job_category:
        query = query.filter(JobListing.job_category.ilike(f"%{job_category.strip()}%"))

    if location:
        query = query.filter(JobListing.location.ilike(f"%{location.strip()}%"))

    if min_salary is not None:
        query = query.filter(
            or_(
                JobListing.salary_max >= min_salary,
                JobListing.is_negotiable == True
            )
        )

    total = query.count()
    jobs = query.order_by(JobListing.created_at.desc()).offset(skip).limit(limit).all()

    items = [format_job_item(j) for j in jobs]
    return JobListResponse(total=total, jobs=items)

@router.get("/{id}", response_model=JobDetailResponse)
def get_job_detail(id: int, db: Session = Depends(get_db)):
    """EP-08: Get detailed job view with full requirements and external apply link"""
    job = db.query(JobListing).filter(JobListing.id == id, JobListing.is_active == True).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Job listing with ID {id} not found",
                    "details": []
                }
            }
        )

    item = format_job_item(job)
    return JobDetailResponse(
        **item.model_dump(),
        description=job.description,
        created_at=job.created_at
    )


@router.post("/ingest", response_model=JobIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_job_endpoint(
    payload: JobIngestRequest,
    db: Session = Depends(get_db)
):
    """EP-26: Automated Job Ingestion Endpoint for n8n, crawlers, and external pipelines."""
    # 1. Automatic Multilingual Job Classification
    classification = classify_job(
        title=payload.title,
        description=payload.description or "",
        company=payload.company
    )

    # 2. Prepare structured dictionary
    job_dict = {
        "title": payload.title,
        "company": payload.company,
        "location": payload.location or "Phnom Penh",
        "description": payload.description or "",
        "source": payload.source or "Telegram",
        "source_url": payload.source_url or f"https://t.me/internshipscambodia/{payload.title.lower().replace(' ', '_')}",
        "salary_min": payload.salary_min,
        "salary_max": payload.salary_max,
        "salary_currency": payload.salary_currency or "USD",
        "is_negotiable": payload.is_negotiable,
        "job_type": payload.job_type or "full-time",
        "experience_level": payload.experience_level or "entry",
        "work_arrangement": payload.work_arrangement or "on-site",
        "apply_email": payload.apply_email,
        "apply_phone": payload.apply_phone,
        "apply_telegram": payload.apply_telegram,
        "skills": payload.skills,
        "job_category": classification.get("job_category", "Information Technology"),
        "job_subcategory": classification.get("job_subcategory", "General"),
        "job_level": classification.get("job_level", "Junior"),
        "classification_confidence": classification.get("classification_confidence", 0.9),
        "classification_source": classification.get("classification_source", "rule")
    }

    # 3. Save with 3-tier Deduplication and 3NF Company Resolution
    target_job, is_new_record, duplicate_of_id = save_job_with_dedup(db=db, job_data=job_dict)
    db.commit()
    db.refresh(target_job)

    is_dup = (duplicate_of_id is not None) or (not is_new_record)
    dup_id = duplicate_of_id or (target_job.id if not is_new_record else None)

    if duplicate_of_id is not None:
        status_str = "merged_duplicate"
    elif not is_new_record:
        status_str = "existing_duplicate"
    else:
        status_str = "created"

    return JobIngestResponse(
        job_id=target_job.id,
        title=target_job.title,
        company=target_job.company,
        canonical_company_id=target_job.company_id,
        is_duplicate=is_dup,
        duplicate_of=dup_id,
        job_category=target_job.job_category or classification.get("job_category", "Information Technology"),
        job_subcategory=target_job.job_subcategory or classification.get("job_subcategory", "General"),
        job_level=target_job.job_level or classification.get("job_level", "Junior"),
        status=status_str
    )
