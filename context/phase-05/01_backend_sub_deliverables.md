# Phase 5.1 — Backend Sub-Deliverables

**Objective:** Build the backend in four small, verifiable pieces so that you always have something working, and record how to rebuild the database from scratch.

**Status:** Submitted · **Last updated:** 2026-10-19

## Done When

- [x] SD-1 to SD-4 are Done, each with verification evidence
- [x] Every Must-Have endpoint passes in your API test collection (shown in Phase 5.2)
- [x] The runbook rebuilds the database from scratch (reset, migrate, seed) on a fresh clone
- [x] No real secrets are committed; `backend/.env.example` lists every variable

## 1. Sub-Deliverables

| SD | Scope | Done when | Endpoints | Target date | Status | Evidence |
|---|---|---|---|---|---|---|
| SD-1 | Database setup & migrations | All Phase 3.3 tables are created in PostgreSQL with indexes, relationships, and test seed data loads | none | 2026-10-18 | Done | `backend/app/models/models.py`, `backend/seed.py` |
| SD-2 | Authentication & authorization | Register, login, token issuing, and middleware that protects routes and checks roles (`user`, `admin`) | EP-02, EP-03 | 2026-10-18 | Done | `backend/app/api/auth.py`, `backend/app/api/deps.py` |
| SD-3 | Core CRUD entities | Create/read/update/delete for the primary resources: profiles, skills, jobs, bookmarks | EP-04, EP-05, EP-06, EP-07, EP-08, EP-10, EP-11, EP-12 | 2026-10-18 | Done | `backend/app/api/profile.py`, `jobs.py`, `skills.py`, `saved_jobs.py` |
| SD-4 | Complex business logic & AI matching | Dual-metric AI job recommendation engine (`required_skill_coverage` + `semantic_similarity` -> `ranking_score`), data cleaning pipeline, background auto-scraper | EP-01, EP-09, EP-13 | 2026-10-18 | Done | `backend/app/services/matching_engine.py`, `importer.py`, `scheduler.py` |

## 2. Implementation Notes

- **SD-1 (Database Setup):** Tables created in PostgreSQL 16 Alpine Docker container with SQLAlchemy ORM declarative models. Created 7 tables: `users`, `profiles`, `skills`, `profile_skills`, `job_listings`, `job_skills`, `saved_jobs`. Seed script seeds 15 standard tech skills and test candidate & admin accounts.
- **SD-2 (Authentication & Security):** Cryptographic password hashing using `bcrypt`. Stateless JWT Bearer tokens signed with HMAC-SHA256. Role-Based Access Control (`role == "admin"`) enforced via FastAPI dependency injection.
- **SD-3 (Core CRUD Resources):** All endpoints implement Pydantic V2 request/response schema validation. Job discovery supports search by title, company, description, and filter by source (JobNet, BongThom, Khmer24, Telegram), experience level, and location.
- **SD-4 (AI Engine & Auto-Scraping):**
  - AI engine combines explainable skill coverage with dense multilingual vector embeddings via `paraphrase-multilingual-MiniLM-L12-v2` (384-dimensional dense vectors supporting English + Khmer Unicode script).
  - Background async scheduler polls and syncs active channels on an hourly schedule (every 60 minutes) non-blockingly.

## 3. Environment & Database Migration Runbook

| Task | Command |
|---|---|
| Create the env file | `cp backend/.env.example backend/.env` |
| Start the database | `docker compose up -d db` |
| Create tables & run seeds | `cd backend && python seed.py` |
| Reset the database | `docker compose down -v && docker compose up -d db && cd backend && python seed.py` |
| Start the API on port 8000 | `cd backend && uvicorn main:app --reload --port 8000` |
| Run the API test collection | `cd backend && PYTHONPATH=. pytest -v` |
| Check health endpoint | `curl http://localhost:8000/api/v1/health` |

### Seeded Test Accounts (Local Testing Only):

| Role | Email | Password | Purpose |
|---|---|---|---|
| Admin | `rith512@gmail.com` | `12345678` | System admin, EP-13 scraping triggers, admin stats |
| Candidate | `dara@example.com` | `Password123!` | Test candidate with Flutter/Dart skills for AI matching |
