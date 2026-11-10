import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import SessionLocal
from app.models.models import Company, CompanyAlias, JobListing

client = TestClient(app)


def test_list_companies_endpoint():
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_resolve_company_api_endpoint():
    payload = {
        "raw_name": "ABA Bank (Cambodia) Plc."
    }
    response = client.post("/api/v1/companies/resolve", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["resolved"] is True
    assert data["normalized_name"] == "aba bank"
    assert "ABA Bank" in data["company"]["name"]
    assert data["company"]["slug"] == "aba-bank"


def test_get_company_detail_and_jobs_endpoint():
    # 1. Resolve to ensure company exists in DB
    client.post("/api/v1/companies/resolve", json={"raw_name": "Smart Axiata Co., Ltd."})

    with SessionLocal() as db:
        comp = db.query(Company).filter(Company.normalized_name == "smart axiata").first()
        assert comp is not None
        comp_id = comp.id

    # 2. Get company detail
    response = client.get(f"/api/v1/companies/{comp_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == comp_id
    assert "active_jobs_count" in data

    # 3. Get company jobs
    jobs_resp = client.get(f"/api/v1/companies/{comp_id}/jobs")
    assert jobs_resp.status_code == 200
    assert isinstance(jobs_resp.json(), list)


def test_get_nonexistent_company_returns_404():
    response = client.get("/api/v1/companies/99999999")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"]["code"] == "COMPANY_NOT_FOUND"

