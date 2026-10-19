import uuid
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_auth_and_profile_flow():
    # 1. Register a new user (EP-02)
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    password = "SecurePassword123!"

    reg_res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": password
    })
    assert reg_res.status_code == 201, reg_res.text
    reg_data = reg_res.json()
    assert reg_data["email"] == unique_email
    assert "token" in reg_data

    # 2. Login (EP-03)
    login_res = client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": password
    })
    assert login_res.status_code == 200, login_res.text
    login_data = login_res.json()
    assert "access_token" in login_data
    token = login_data["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    # 3. Get Candidate Profile (EP-04)
    profile_res = client.get("/api/v1/profile", headers=headers)
    assert profile_res.status_code == 200, profile_res.text
    profile_data = profile_res.json()
    assert profile_data["user_id"] == reg_data["user_id"]

    # 4. Update Candidate Profile and Skills (EP-05)
    update_res = client.put("/api/v1/profile", headers=headers, json={
        "full_name": "Sreymom Mean",
        "education": "Computer Science, Year 4",
        "experience_level": "entry",
        "preferred_role": "Junior Flutter Developer",
        "preferred_location": "Phnom Penh",
        "expected_salary": 350.00,
        "skills": ["Flutter", "Dart", "Firebase", "Git"]
    })
    assert update_res.status_code == 200, update_res.text
    updated_data = update_res.json()
    assert updated_data["full_name"] == "Sreymom Mean"
    assert "Flutter" in updated_data["skills"]
    assert "Dart" in updated_data["skills"]

def test_unauthorized_profile_access():
    """Verify endpoint protection without valid token"""
    res = client.get("/api/v1/profile")
    assert res.status_code == 401
