import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import Company, CompanyAlias, JobListing
from app.services.company_resolver import resolve_company, generate_company_slug
from app.services.dedup_manager import save_job_with_dedup


@pytest.fixture
def db_session():
    """In-memory SQLite database for testing company resolution."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_generate_company_slug():
    assert generate_company_slug("ABA Bank") == "aba-bank"
    assert generate_company_slug("Smart Axiata Co., Ltd.") == "smart-axiata-co-ltd"
    assert generate_company_slug("🔥 Hot Startup 2026") == "hot-startup-2026"


def test_resolve_new_company(db_session):
    company, is_new = resolve_company(
        db=db_session,
        raw_company_name="ABA Bank (Cambodia) Plc.",
        logo_url="https://example.com/aba.png"
    )
    db_session.commit()

    assert is_new is True
    assert company is not None
    assert company.id is not None
    assert company.name == "ABA Bank (Cambodia) Plc."
    assert company.normalized_name == "aba bank"
    assert company.slug == "aba-bank"
    assert company.logo_url == "https://example.com/aba.png"


def test_resolve_existing_company_canonical_match(db_session):
    # First creation
    comp1, is_new1 = resolve_company(db=db_session, raw_company_name="Smart Axiata")
    db_session.commit()
    assert is_new1 is True

    # Second incoming job with legal suffix
    comp2, is_new2 = resolve_company(db=db_session, raw_company_name="Smart Axiata Co., Ltd.")
    assert is_new2 is False
    assert comp2.id == comp1.id


def test_resolve_company_alias(db_session):
    # Create canonical company
    comp, _ = resolve_company(db=db_session, raw_company_name="ABA Bank")
    db_session.commit()

    # Add verified alias for alternative legal name
    alias = CompanyAlias(
        company_id=comp.id,
        alias_name="Advanced Bank of Asia Ltd",
        normalized_alias="advanced bank of asia",
        is_verified=True
    )
    db_session.add(alias)
    db_session.commit()

    # Now scrape an incoming job with the alternative legal name
    resolved, is_new = resolve_company(db=db_session, raw_company_name="Advanced Bank of Asia Ltd")
    assert is_new is False
    assert resolved.id == comp.id


def test_save_job_with_dedup_links_company_id(db_session):
    job_payload = {
        "title": "Flutter Developer",
        "company": "Wing Bank (Cambodia) Plc.",
        "location": "Phnom Penh",
        "source": "Telegram",
        "source_post_id": "9991",
        "source_url": "https://t.me/jobs/9991"
    }

    job, is_new, _ = save_job_with_dedup(db=db_session, job_data=job_payload)
    db_session.commit()

    assert job.id is not None
    assert job.company_id is not None

    canonical_comp = db_session.query(Company).filter(Company.id == job.company_id).first()
    assert canonical_comp is not None
    assert canonical_comp.normalized_name == "wing bank"

