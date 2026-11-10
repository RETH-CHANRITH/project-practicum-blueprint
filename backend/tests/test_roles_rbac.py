import uuid
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.database import SessionLocal
from app.models.models import User, Company

client = TestClient(app)

def test_user_role_permissions_and_restrictions():
    """
    Test Role 1: 'user' (Candidate / Student)
    - Can register and login as a candidate
    - Can access profile, recommendations, and search jobs
    - CANNOT access admin endpoints (strictly 403 Forbidden)
    """
    db = SessionLocal()
    try:
        unique_email = f"candidate_{uuid.uuid4().hex[:8]}@example.com"
        password = "Password123!"

        # 1. Register candidate (role defaults to 'user')
        reg_res = client.post("/api/v1/auth/register", json={
            "email": unique_email,
            "password": password
        })
        assert reg_res.status_code == 201, reg_res.text
        
        # Verify in DB that role is strictly 'user'
        user_in_db = db.query(User).filter(User.email == unique_email).first()
        assert user_in_db is not None
        assert user_in_db.role == "user"

        # 2. Login as candidate
        login_res = client.post("/api/v1/auth/login", json={
            "email": unique_email,
            "password": password
        })
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        user_headers = {"Authorization": f"Bearer {token}"}

        # 3. Candidate CAN access user profile (200 OK)
        profile_res = client.get("/api/v1/profile", headers=user_headers)
        assert profile_res.status_code == 200

        # 4. Candidate CAN search jobs (200 OK)
        jobs_res = client.get("/api/v1/jobs?limit=5")
        assert jobs_res.status_code == 200

        # 5. Candidate CAN access recommendations (200 OK)
        rec_res = client.get("/api/v1/recommendations", headers=user_headers)
        assert rec_res.status_code == 200

        # 6. Candidate CANNOT access Admin Stats (403 Forbidden)
        admin_stats_res = client.get("/api/v1/admin/stats", headers=user_headers)
        assert admin_stats_res.status_code == 403
        err = admin_stats_res.json()["detail"]["error"]
        assert err["code"] == "FORBIDDEN"
        assert "Admin privileges required" in err["message"]

        # 7. Candidate CANNOT trigger scraper endpoint (403 Forbidden)
        admin_scrape_res = client.post("/api/v1/admin/scrape", headers=user_headers, json={"source": "khmer24"})
        assert admin_scrape_res.status_code == 403
        assert admin_scrape_res.json()["detail"]["error"]["code"] == "FORBIDDEN"

    finally:
        db.close()


def test_admin_role_permissions():
    """
    Test Role 2: 'admin' (System Administrator)
    - Admin can log in
    - Admin has role == 'admin'
    - Admin CAN access admin endpoints (200 OK)
    """
    db = SessionLocal()
    try:
        from app.core.security import hash_password
        admin_email = f"admin_{uuid.uuid4().hex[:8]}@jobmatch.com"
        admin_pass = "AdminSecret123!"

        # Create admin user directly in DB
        admin_user = User(
            email=admin_email,
            password_hash=hash_password(admin_pass),
            role="admin"
        )
        db.add(admin_user)
        db.commit()

        # 1. Login as Admin
        login_res = client.post("/api/v1/auth/login", json={
            "email": admin_email,
            "password": admin_pass
        })
        assert login_res.status_code == 200
        admin_token = login_res.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 2. Admin CAN access Admin Stats (200 OK)
        stats_res = client.get("/api/v1/admin/stats", headers=admin_headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert "total_candidates" in stats
        assert "total_jobs" in stats
        assert "active_sources" in stats

    finally:
        db.close()


def test_no_employer_role_and_zero_employer_portal():
    """
    Test Architectural Boundaries:
    - Registering cannot inject 'employer' or 'admin' role
    - No employer registration or login routes exist
    - Company entities do NOT have user credentials
    """
    db = SessionLocal()
    try:
        # 1. Attempt to register with role="admin" or role="employer"
        hack_email = f"attacker_{uuid.uuid4().hex[:8]}@example.com"
        res = client.post("/api/v1/auth/register", json={
            "email": hack_email,
            "password": "Password123!",
            "role": "admin"  # Pydantic schema will ignore or disallow privilege escalation
        })
        assert res.status_code == 201
        
        # Verify DB strictly forced role to 'user'
        user_db = db.query(User).filter(User.email == hack_email).first()
        assert user_db.role == "user", "Role escalation vulnerability: user gained non-user role!"

        # 2. Verify non-existent employer endpoints return 404
        assert client.post("/api/v1/employer/register").status_code == 404
        assert client.post("/api/v1/employer/login").status_code == 404
        assert client.post("/api/v1/company/post-job").status_code == 404

        # 3. Verify Company table has NO authentication fields
        assert not hasattr(Company, "password_hash")
        assert not hasattr(Company, "email")
        assert not hasattr(Company, "role")

    finally:
        db.close()

