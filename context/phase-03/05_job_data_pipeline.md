# Phase 3.5 — Job Data Pipeline Architecture

**Objective:** Document the end-to-end Extract, Transform, Load (ETL) data pipeline that ingests, cleans, standardizes, deduplicates, and stores Cambodian recruitment posts for the AI recommendation engine.

**Status:** Draft · **Last updated:** 2026-11-04

---

## 1. Editable Diagram Link (Draw.io / Google Drive)

> [!TIP]
> **Draw.io Source Diagram:**  
> The editable vector diagram source file is hosted on Google Drive:  
> 🔗 **[Open / Download Draw.io Diagram File on Google Drive](https://drive.google.com/file/d/1EH3s90BtcGFPcgdMEFUoFmLql04RyMis/view?usp=sharing)**
> 
> **How to open in Draw.io:**
> 1. Visit [app.diagrams.net](https://app.diagrams.net/)
> 2. Click **File** ➔ **Open From** ➔ **Google Drive** (or download the file from the link and choose **Device**)
> 3. You can edit nodes, connectors, and colors directly.

---

## 2. Pipeline Architecture Flowchart

![Job Data Pipeline Diagram](../assets/job_data_pipeline_diagram.png)

---

## 3. Pipeline Stages Breakdown

The JobMatch Cambodia data pipeline operates in **5 sequential stages**:

### Stage 1: Job Data Types (Raw Input Sources)
Recruitment opportunities in Cambodia are published across fragmented channels with varying structures:
1. **Telegram Channels (`@internshipscambodia`, `@camhr_jobs`):**
   - **Type:** Unstructured free-form text.
   - **Characteristics:** Written in mixed Khmer and English, containing decorative emojis (`🔥`, `⚡`, `📢`), unformatted salary strings, and inline contact handles without schema.
2. **Web Job Portals (CamHR, BongThom, JobNet):**
   - **Type:** Semi-structured HTML DOM.
   - **Characteristics:** Job cards organized with CSS class selectors across paginated listing pages, containing job title, company name, salary range, and deadline.
3. **Company Direct Post / API:**
   - **Type:** Structured JSON payload.
   - **Characteristics:** Pre-validated key-value pairs submitted by verified employers via the JobMatch employer portal (`POST /api/v1/jobs/ingest`).

---

### Stage 2: Scraping & Ingestion Engine
Handles automated data collection and staging:
1. **Telegram Scraper (`backend/app/services/scraper.py`):**
   - Built on `Telethon` (MTProto client protocol).
   - Listens to incoming messages in real time from public Cambodian job channels.
   - Extracts raw message text, timestamp, channel ID, and media links.
2. **Web Crawler Engine (`requests` + `BeautifulSoup4`):**
   - Sends automated HTTP requests to job boards.
   - Traverses pagination links and parses target HTML DOM tags with CSS selectors.
   - Applies rate-limiting and exponential backoff retry mechanisms to respect web policies.
3. **Raw Payload Storage Layer:**
   - All three incoming streams converge into a raw ingestion table before any destructive processing.
   - Preserves `raw_payload`, `source_type` (`telegram` | `camhr` | `direct`), and `source_url` for full auditability and traceability.

---

### Stage 3: Processing & Normalization
Converts noisy raw text into clean, structured fields:
1. **Text Sanitization (Python Regex Engine):**
   - Strips non-standard emojis and decorative unicode characters.
   - Removes HTML tags (`<br>`, `<p>`, `<span>`, `<div>`) and extra whitespaces.
   - Removes marketing noise words (e.g., *"Urgent Hiring!"*, *"Apply Now"*, *"Hot Job 2026"*).
   - Cleans corporate legal suffixes (e.g., `"ABA Bank Co., Ltd"` $\rightarrow$ `"ABA Bank"`).
2. **Deterministic NLP Field Parsers:**
   - **Salary Parser:** Converts irregular salary text (e.g., `"$300 - $500/month"`) into structured numerical fields: `salary_min = 300.0`, `salary_max = 500.0`, `salary_currency = "USD"`.
   - **Location Normalizer:** Maps local variations (`"PP"`, `"PhnomPenh"`, `"រាជធានីភ្នំពេញ"`) to a single canonical city name: `"Phnom Penh"`.
   - **Contact Parser:** Extracts phone numbers (`012 xxx xxx`), HR emails, and Telegram usernames (`@recruiter`).
   - **Deadline Parser:** Normalizes date formats (`30-Nov-2026`, `30/11/2026`) into standard ISO-8601 timestamps (`2026-11-30T00:00:00Z`).
   - **Openings Parser:** Extracts number of vacancies (e.g., `"2 positions"` $\rightarrow$ `openings_count = 2`).
3. **AI Job Classification (`job_classifier.py`):**
   - Classifies canonical `job_category` (e.g., `SOFTWARE_ENGINEERING`, `DESIGN`, `MARKETING`, `FINANCE`).
   - Determines seniority `job_level` (`INTERNSHIP`, `ENTRY`, `JUNIOR`, `SENIOR`).
   - Uses hybrid approach: cloud Jev AI classification with automatic fallback to local rule-based keyword matching.

---

### Stage 4: Merge Data & Skill Standardization
Eliminates cross-platform duplicate postings and normalizes technology skill keywords:

1. **Skill Standardization (`dedup_manager.py`):**
   - Scans cleaned job descriptions against a **Master Skills Catalog** and alias mapping dictionary.
   - Normalizes synonyms to canonical skill records:
     - `"ReactJS"` / `"React.js"` / `"React JS"` $\rightarrow$ canonical **`React`**
     - `"node.js"` / `"NodeJS"` $\rightarrow$ canonical **`Node.js`**
     - Splits compound phrases: `"Flutter/Dart"` $\rightarrow$ **`Flutter`** + **`Dart`**
   - Creates many-to-many associations in `job_skills` join table.
2. **3-Tier Deduplication Engine:**
   - **Tier 1 — Exact SHA-256 Hash Match:** Checks precomputed `dedup_hash = SHA256(norm_title + norm_company + location)`.
   - **Tier 2 — Contact + Title Fuzzy Similarity ($\ge 80\%$):** Matches shared Telegram handle or HR email combined with title string similarity $\ge 80\%$.
   - **Tier 3 — RapidFuzz Token Sort Ratio ($\ge 90\%$):** Compares combined company name and job title using `RapidFuzz` string matching.
3. **Smart Data Merging:**
   - The earliest published post is marked as the **Canonical Primary Job**.
   - Fills missing fields from the duplicate record into the primary record (e.g., salary extracted from CamHR supplements a Telegram post that lacked salary details).
   - Sets `duplicate_of = primary_job.id` on duplicate records so they are hidden from user search results.

---

### Stage 5: Storage & AI Recommendation
Delivers processed data to the end user:
1. **PostgreSQL Relational Database:**
   - Persists clean records in relational tables: `job_listings`, `job_skills`, and `companies`.
2. **AI Recommendation Engine (`matching_engine.py`):**
   - Loads student profile skills and job listing skills.
   - Applies **TF-IDF Vectorization** (scikit-learn `TfidfVectorizer`) and **Cosine Similarity**.
   - Calculates personalized `match_score` ($0\% - 100\%$) for each active job.
3. **Flutter Mobile Client:**
   - Queries `GET /api/v1/recommendations`.
   - Displays ranked internship and junior job cards with matching percentages directly to students.

---

## 4. End-to-End Concrete Example

### Step 1: Raw Ingested Text (Telegram Post)
```text
🔥 URGENT HIRING!! 🔥
Company: ABA Bank (Cambodia) Plc.
Position: Junior Flutter Mobile Developer (2 positions)
Location: Phnom Penh
Salary: $400 - $650 / month
Requirements:
- Good knowledge of Flutter/Dart, RESTful API, Git
- Fresh grads welcome!
Deadline: 30-Nov-2026
Apply CV to: @aba_recruitment or hr@ababank.com
```

### Step 2: Final Database Entity (`job_listings` in PostgreSQL)
```json
{
  "id": 1042,
  "title": "Junior Flutter Mobile Developer",
  "company_name": "ABA Bank",
  "job_category": "SOFTWARE_ENGINEERING",
  "job_level": "JUNIOR",
  "location": "Phnom Penh",
  "salary_min": 400.00,
  "salary_max": 650.00,
  "salary_currency": "USD",
  "openings_count": 2,
  "application_deadline": "2026-11-30T00:00:00Z",
  "contact_telegram": "aba_recruitment",
  "contact_email": "hr@ababank.com",
  "standardized_skills": [
    {"id": 12, "name": "Flutter"},
    {"id": 13, "name": "Dart"},
    {"id": 45, "name": "RESTful API"},
    {"id": 50, "name": "Git"}
  ],
  "dedup_hash": "a8f3...b291",
  "duplicate_of": null,
  "source_type": "telegram"
}
```

---

## 5. Component & Codebase Traceability

| Stage | Responsible Component | Key Source Code Files |
|---|---|---|
| **1. Input** | External Feeds | Telegram Channels, CamHR HTML, Direct API |
| **2. Scraping** | `ScraperService` | `backend/app/services/scraper.py` |
| **3. Processing** | Deterministic Parsers & Classifier | `backend/app/services/scraper.py`, `job_classifier.py` |
| **4. Merge & Standard** | `DedupManager` | `backend/app/services/dedup_manager.py` |
| **5. Storage & AI** | PostgreSQL & `MatchingEngine` | `backend/app/models/models.py`, `backend/app/services/matching_engine.py` |

