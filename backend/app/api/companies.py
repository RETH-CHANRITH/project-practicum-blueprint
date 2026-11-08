from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.database import get_db
from app.models.models import Company, CompanyAlias, JobListing
from app.schemas.schemas import (
    CompanyResponse,
    CompanyDetailResponse,
    CompanyAliasResponse,
    CompanyResolveRequest,
    CompanyResolveResponse,
    JobItemResponse
)
from app.services.company_resolver import resolve_company, normalize_company_name

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", response_model=List[CompanyResponse])
def list_companies(
    q: Optional[str] = Query(None, description="Search company name or keyword"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    is_verified: Optional[bool] = Query(None, description="Filter verified employers"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List canonical hiring companies with active job counts."""
    query = db.query(Company)

    if q:
        norm_q = normalize_company_name(q)
        query = query.filter(
            or_(
                Company.name.ilike(f"%{q}%"),
                Company.normalized_name.ilike(f"%{norm_q}%"),
                Company.slug.ilike(f"%{norm_q}%")
            )
        )

    if industry:
        query = query.filter(Company.industry.ilike(f"%{industry}%"))

    if is_verified is not None:
        query = query.filter(Company.is_verified == is_verified)

    companies = query.order_by(Company.name.asc()).offset(offset).limit(limit).all()

    # Enrich with active job counts
    result = []
    for c in companies:
        count = db.query(func.count(JobListing.id)).filter(
            JobListing.company_id == c.id,
            JobListing.is_active == True,
            JobListing.duplicate_of.is_(None)
        ).scalar() or 0
        c_dict = CompanyResponse.model_validate(c)
        c_dict.active_jobs_count = count
        result.append(c_dict)

    return result


@router.get("/{id}", response_model=CompanyDetailResponse)
def get_company(id: int, db: Session = Depends(get_db)):
    """Retrieve full company profile with aliases and active job count."""
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "COMPANY_NOT_FOUND",
                    "message": f"Company with ID {id} not found",
                    "details": []
                }
            }
        )

    count = db.query(func.count(JobListing.id)).filter(
        JobListing.company_id == company.id,
        JobListing.is_active == True,
        JobListing.duplicate_of.is_(None)
    ).scalar() or 0

    response = CompanyDetailResponse.model_validate(company)
    response.active_jobs_count = count
    return response


@router.get("/{id}/jobs", response_model=List[JobItemResponse])
def get_company_jobs(
    id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Retrieve active canonical job listings published by a specific company."""
    company = db.query(Company).filter(Company.id == id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "COMPANY_NOT_FOUND",
                    "message": f"Company with ID {id} not found",
                    "details": []
                }
            }
        )

    jobs = db.query(JobListing).filter(
        JobListing.company_id == company.id,
        JobListing.is_active == True,
        JobListing.duplicate_of.is_(None)
    ).order_by(JobListing.posted_at.desc()).offset(offset).limit(limit).all()

    from app.api.jobs import format_job_item
    return [format_job_item(j) for j in jobs]


@router.post("/resolve", response_model=CompanyResolveResponse)
def resolve_company_name_endpoint(
    payload: CompanyResolveRequest,
    db: Session = Depends(get_db)
):
    """Utility endpoint to test and execute 4-tier company entity resolution."""
    raw = (payload.raw_name or payload.company or payload.name or "ABA Bank (Cambodia) Plc.").strip()
    norm = normalize_company_name(raw)

    comp, is_new = resolve_company(
        db=db,
        raw_company_name=raw,
        source_id=payload.source_id,
        auto_create=True
    )
    db.commit()

    if comp:
        comp_resp = CompanyResponse.model_validate(comp)
        return CompanyResolveResponse(
            raw_name=raw,
            normalized_name=norm,
            resolved=True,
            is_new=is_new,
            company=comp_resp
        )
    else:
        return CompanyResolveResponse(
            raw_name=raw,
            normalized_name=norm,
            resolved=False,
            is_new=False,
            company=None
        )
