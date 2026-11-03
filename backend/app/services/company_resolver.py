"""Company Resolution Service

Implements 4-tier Company Entity Resolution (3NF) for JobMatch Cambodia:
  1. Text Normalization & Corporate Suffix Stripping
  2. Exact Canonical Match (normalized_name)
  3. Verified Alias Lookup (company_aliases)
  4. Controlled Fuzzy Candidate Detection / Canonical Ingestion
"""
import re
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from app.models.models import Company, CompanyAlias
from app.services.dedup_manager import normalize_company_name


def generate_company_slug(name: str) -> str:
    """Generate a clean, URL-safe slug for a company."""
    slug = name.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug or "company"


def resolve_company(
    db: Session,
    raw_company_name: str,
    source_id: Optional[int] = None,
    logo_url: Optional[str] = None,
    website_url: Optional[str] = None,
    auto_create: bool = True
) -> Tuple[Optional[Company], bool]:
    """
    Resolve an incoming raw company name string into a canonical Company entity.
    Returns: (Company, is_newly_created)
    """
    if not raw_company_name or not raw_company_name.strip():
        return None, False

    clean_name = raw_company_name.strip()
    norm_name = normalize_company_name(clean_name)
    if not norm_name or len(norm_name) < 2:
        return None, False

    # Tier 1: Exact Match on Canonical normalized_name
    canonical = db.query(Company).filter(Company.normalized_name == norm_name).first()
    if canonical:
        # Enrich missing logo or website
        if not canonical.logo_url and logo_url:
            canonical.logo_url = logo_url
        if not canonical.website_url and website_url:
            canonical.website_url = website_url
        return canonical, False

    # Tier 2: Match on Verified Company Alias
    alias_match = db.query(CompanyAlias).filter(
        CompanyAlias.normalized_alias == norm_name
    ).first()
    if alias_match and alias_match.company:
        return alias_match.company, False

    # Tier 3: Controlled Fuzzy Match against canonical companies
    all_companies = db.query(Company).all()
    for comp in all_companies:
        score = fuzz.token_sort_ratio(comp.normalized_name, norm_name)
        if score >= 95:  # High confidence match
            return comp, False

    # Tier 4: Create New Canonical Company Record
    if not auto_create:
        return None, False

    # Generate unique slug
    base_slug = generate_company_slug(norm_name)
    slug = base_slug
    counter = 1
    while db.query(Company).filter(Company.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    display_name = clean_name
    # Strip obvious noise emoji or prefixes
    display_name = re.sub(r"^[🔥⚡📢\s]+", "", display_name).strip()

    new_company = Company(
        name=display_name,
        normalized_name=norm_name,
        slug=slug,
        logo_url=logo_url,
        website_url=website_url,
        is_verified=False,
        verification_status="unverified"
    )
    db.add(new_company)
    db.flush()  # Flush to get new_company.id

    # If raw name differed significantly from display name, register as observed alias
    if source_id and clean_name.lower() != display_name.lower():
        alias_record = CompanyAlias(
            company_id=new_company.id,
            source_id=source_id,
            alias_name=clean_name,
            normalized_alias=norm_name,
            is_verified=False
        )
        db.add(alias_record)

    return new_company, True

