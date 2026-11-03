# Phase 3.6 — Company Management & Entity Resolution Architecture

**Project:** JobMatch Cambodia — AI-Assisted Job Aggregator & Recommendation Engine  
**Institution:** Royal University of Phnom Penh (RUPP)  
**Architecture:** Relational Database Design (3NF)  
**Module:** Company Management & Entity Resolution  
**Status:** Approved Technical Architecture & Implementation Specification · **Last updated:** 2026-11-04  

---

## 1. Introduction & Core Problem

### 1.1 Definition of Company in JobMatch Cambodia

In JobMatch Cambodia, a **Company** represents the hiring organization (employer) that offers job vacancies and internships.

A company is maintained as a canonical entity in the PostgreSQL database (`companies` table). Multiple job listings reference the same company through a foreign key (`job_listings.company_id`).

The purpose is to maintain consistent employer information across heterogeneous Cambodian recruitment platforms.

### 1.2 The Real-World Cambodian Problem

Recruiters and HR agencies frequently publish the same employer's vacancies across different channels using inconsistent company names:

| Platform | How the Company Name Appears |
|---|---|
| **Telegram** | `🔥 URGENT ABA Bank Plc.` |
| **CamHR** | `Advanced Bank of Asia Ltd (ABA Bank)` |
| **BongThom** | `ABA Bank (Cambodia) Plc.` |
| **JobNet** | `ABA Bank Co., Ltd` |

If these names are treated as independent text strings without standardization, several problems occur:

1. **Fragmented company profiles:** Students see multiple duplicate profiles for the same employer.
2. **Search inconsistency:** Searching for "ABA Bank" misses vacancies published under its alternative legal name.
3. **Deduplication failure:** Job deduplication fails to recognize matching employer identities.
4. **Data redundancy:** Company names, logos, and descriptions are repeatedly stored across hundreds of rows.
5. **Verification difficulties:** Employer verification becomes unmanageable when one organization has multiple records.
6. **Recommendation inconsistency:** Employer-related domain weights become diluted across fragmented records.

### 1.3 Project Objectives

The Company Management module aims to:

- Maintain one canonical company identity for each recognized employer.
- Normalize inconsistent company names collected from different sources.
- Support alternative names through a dedicated company alias system (`company_aliases`).
- Connect multiple job listings to the same canonical company (`1:N`).
- Preserve original scraped company names for complete traceability.
- Support employer verification and authenticity checks (`is_verified`).
- Distinguish hiring organizations from recruitment agencies.
- Provide reliable company information to search and recommendation services.

---

## 2. Complete Relational Database ERD (3NF)

Below is the complete 3NF Entity-Relationship Diagram covering all 8 tables: canonical employers, multi-platform aliases, provenance tracking, conglomerate parent-subsidiary hierarchies, verification audit logs, and recruitment agency disambiguation.

![Company Resolution ERD](../assets/company_resolution_erd.png)

```mermaid
erDiagram
    COMPANIES ||--o{ JOB_LISTINGS : employs
    COMPANIES ||--o{ COMPANY_ALIASES : has
    COMPANIES ||--o{ COMPANY_RELATIONSHIPS : parent_of
    COMPANIES ||--o{ COMPANY_VERIFICATION_LOGS : reviewed_in
    SOURCES ||--o{ COMPANY_ALIASES : discovered_from
    SOURCES ||--o{ JOB_SOURCES : provides
    JOB_LISTINGS ||--o{ JOB_SOURCES : collected_from
    RECRUITMENT_AGENCIES ||--o{ JOB_LISTINGS : publishes_for

    COMPANIES {
        bigint id PK
        varchar name
        varchar normalized_name UK
        varchar slug UK
        text logo_url
        varchar website
        varchar industry
        varchar headquarters
        text description
        boolean is_verified
        varchar verification_status
        varchar verification_method
        timestamptz verified_at
        timestamptz created_at
        timestamptz updated_at
    }

    COMPANY_ALIASES {
        bigint id PK
        bigint company_id FK
        bigint source_id FK
        varchar alias_name
        varchar normalized_alias
        boolean is_verified
        timestamptz created_at
        timestamptz updated_at
    }

    COMPANY_RELATIONSHIPS {
        bigint id PK
        bigint parent_company_id FK
        bigint child_company_id FK
        varchar relationship_type
        timestamptz created_at
    }

    COMPANY_VERIFICATION_LOGS {
        bigint id PK
        bigint company_id FK
        varchar previous_status
        varchar new_status
        varchar verification_method
        text evidence_url
        text notes
        varchar reviewed_by
        timestamptz created_at
    }

    RECRUITMENT_AGENCIES {
        int id PK
        varchar name
        varchar normalized_name UK
        varchar website
        varchar email
        varchar phone
        timestamptz created_at
        timestamptz updated_at
    }

    JOB_LISTINGS {
        int id PK
        int company_id FK
        int recruitment_agency_id FK
        int duplicate_of FK
        varchar title
        varchar company
        numeric salary_min
        numeric salary_max
        varchar dedup_hash
        boolean is_active
        timestamptz posted_at
    }

    JOB_SOURCES {
        bigint id PK
        int job_id FK
        int source_id FK
        varchar original_company_name
        varchar source_job_id
        text source_url
        varchar original_title
        text original_salary
        text original_contact
        timestamptz first_seen_at
        timestamptz last_seen_at
    }

    SOURCES {
        int id PK
        varchar name UK
        varchar code UK
        varchar platform_type
        text url
        boolean is_active
    }
```

---

## 3. Detailed Database Schema Specifications

### 3.1 Table: `companies` (Canonical Employer Table)
Stores single authoritative brand identities.

| Column | Data Type | Constraints | Nullable | Description & Example |
|---|---|---|---|---|
| `id` | `BIGINT` / `INTEGER` | `PRIMARY KEY`, `SERIAL` | **No** | Unique canonical company ID (e.g. `15`) |
| `name` | `VARCHAR(255)` | `INDEX` | **No** | Primary display brand name (e.g. `"ABA Bank"`) |
| `normalized_name` | `VARCHAR(255)` | `UNIQUE`, `INDEX` | **No** | Lowercase sanitized token for $O(\log n)$ lookup (`"aba bank"`) |
| `slug` | `VARCHAR(255)` | `UNIQUE`, `INDEX` | **No** | Clean URL slug for routing (`"aba-bank"`) |
| `logo_url` | `TEXT` | | **Yes** | Image URL to official corporate logo |
| `website` | `VARCHAR(500)` | | **Yes** | Official company homepage (`"https://www.ababank.com"`) |
| `industry` | `VARCHAR(100)` | `INDEX` | **Yes** | Domain sector (`"Banking & Finance"`, `"Information Technology"`) |
| `headquarters` | `VARCHAR(255)` | `DEFAULT 'Phnom Penh'` | **No** | Head office city location |
| `description` | `TEXT` | | **Yes** | Overview of business, culture, and mission |
| `is_verified` | `BOOLEAN` | `DEFAULT FALSE`, `INDEX` | **No** | Anti-impersonation badge (`TRUE` if verified) |
| `verification_status`| `VARCHAR(20)` | `DEFAULT 'unverified'` | **No** | `unverified` \| `pending` \| `verified` \| `rejected` |
| `verification_method`| `VARCHAR(100)` | | **Yes** | Evidence (`"business_registration"`, `"official_domain"`) |
| `verified_at` | `TIMESTAMPTZ` | | **Yes** | Timestamp of verification approval |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | **No** | Ingestion timestamp |
| `updated_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | **No** | Profile update timestamp |

---

### 3.2 Table: `company_aliases` (Multi-Platform Brand Mapping)
Maps observed spelling variations, legal names, and Khmer transliterations to canonical companies.

| Column | Data Type | Constraints | Nullable | Description & Example |
|---|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `SERIAL` | **No** | Unique alias identifier |
| `company_id` | `BIGINT` | `FK → companies.id ON DELETE CASCADE`, `INDEX` | **No** | Linked canonical company |
| `source_id` | `BIGINT` | `FK → sources.id ON DELETE SET NULL`, `INDEX` | **Yes** | Platform where this alias was scraped |
| `alias_name` | `VARCHAR(255)` | | **No** | Raw observed name (`"Advanced Bank of Asia Ltd"`) |
| `normalized_alias` | `VARCHAR(255)` | `INDEX` | **No** | Cleaned lookup key (`"advanced bank of asia"`) |
| `is_verified` | `BOOLEAN` | `DEFAULT FALSE` | **No** | `TRUE` if verified by admin; unverified aliases require checks |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | **No** | Timestamp when alias was recorded |

```sql
CONSTRAINT uq_company_aliases_company_alias UNIQUE (company_id, normalized_alias);
```

---

### 3.3 Table: `company_relationships` (Conglomerate & Subsidiary Model)
Prevents merging parent conglomerates and their operating subsidiaries.

| Column | Data Type | Constraints | Nullable | Description & Example |
|---|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `SERIAL` | **No** | Relationship identifier |
| `parent_company_id` | `BIGINT` | `FK → companies.id ON DELETE CASCADE`, `INDEX` | **No** | Parent company (e.g. Chip Mong Group) |
| `child_company_id` | `BIGINT` | `FK → companies.id ON DELETE CASCADE`, `INDEX` | **No** | Subsidiary (e.g. Chip Mong Insee Cement) |
| `relationship_type` | `VARCHAR(50)` | `DEFAULT 'subsidiary'` | **No** | `'subsidiary'`, `'joint_venture'`, `'branch'` |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | **No** | Relationship creation timestamp |

```sql
CONSTRAINT chk_company_no_self_parent CHECK (parent_company_id != child_company_id);
```

---

### 3.4 Table: `company_verification_logs` (Audit Trail)
Tracks administrative changes and verification evidence.

| Column | Data Type | Constraints | Nullable | Description |
|---|---|---|---|---|
| `id` | `BIGINT` | `PRIMARY KEY`, `SERIAL` | **No** | Unique log identifier |
| `company_id` | `BIGINT` | `FK → companies.id ON DELETE CASCADE`, `INDEX` | **No** | Evaluated company |
| `previous_status` | `VARCHAR(20)` | | **No** | Status prior to update |
| `new_status` | `VARCHAR(20)` | | **No** | New approved status |
| `verification_method`| `VARCHAR(50)` | | **No** | Verification channel (`'manual_review'`, `'tax_id'`) |
| `evidence_url` | `TEXT` | | **Yes** | Document URL or company email domain link |
| `notes` | `TEXT` | | **Yes** | Administrative comments |
| `reviewed_by` | `VARCHAR(100)` | | **Yes** | Admin username or reviewer email |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT NOW()` | **No** | Audit entry timestamp |

---

### 3.5 Table: `recruitment_agencies` & Disambiguation
Prevents recruitment firms (e.g., Top Recruitment, CamHR Agency) from being mistaken for the actual employer.

In `job_listings`:
- **`company_id`** (`INTEGER`, `FK → companies.id`, `NULL`): Points to the actual hiring bank or tech company.
- **`recruitment_agency_id`** (`INTEGER`, `FK → recruitment_agencies.id`, `NULL`): Points to the recruitment firm managing the post.
- **Confidential Vacancy Rule:** If an agency advertises a post with an undisclosed employer, `company_id` is left `NULL`. The agency is **never** assigned as the employer!

---

## 4. 6-Stage Resolution Flowchart

The system executes company resolution **before** job deduplication so that the matching engine compares canonical integer IDs (`company_id == 15`) rather than error-prone raw strings.

![Company Resolution Flowchart](../assets/company_resolution_flowchart.png)

```mermaid
flowchart TD
    A["Stage 1: Ingest Raw Job<br/>(e.g., '🔥 URGENT ABA Bank (Cambodia) Plc.')"] --> B["Stage 2: Deterministic Normalization<br/>Strip emojis, noise prefixes, legal suffixes ('plc', 'co., ltd')<br/>$\rightarrow$ 'aba bank'"]
    B --> C{"Stage 3: Tier 1<br/>Exact Canonical Match?<br/>companies.normalized_name == 'aba bank'"}
    
    C -- "[YES - 100% Match]" --> H["Stage 4: Retrieve Canonical company_id<br/>(e.g., ID: 15)<br/>Enrich missing logo/website"]
    
    C -- "[NO]" --> D{"Stage 3: Tier 2<br/>Verified Alias Match?<br/>company_aliases.normalized_alias == 'aba bank'"}
    
    D -- "[YES - Verified Alias]" --> H
    
    D -- "[NO]" --> E{"Stage 3: Tier 3<br/>RapidFuzz Ratio >= 90%?<br/>Generate Candidate Employers"}
    
    E -- "[YES - Candidate]" --> F{"Stage 4: Evidence Evaluation<br/>Shared recruiter email domain (@ababank.com)?<br/>Same corporate website or registered address?"}
    
    F -- "[YES - Evidence Confirmed]" --> H
    F -- "[NO / Uncertain]" --> G{"Agency or Confidential?"}
    E -- "[NO Match]" --> G
    
    G -- "[Agency / Undisclosed]" --> I["Keep company_id = NULL<br/>Preserve original scraped name"]
    G -- "[Genuinely New Employer]" --> J["Insert New Canonical Company<br/>Set is_verified = FALSE<br/>Assign new company_id"]
    
    H --> K["Stage 5: Preserve Source Provenance<br/>Record original scraped name in job_sources"]
    I --> K
    J --> K
    
    K --> L["Stage 6: Hand-off to Job Deduplication Engine<br/>Compute dedup_hash with company_id<br/>Check duplicate_of star topology"]
    L --> M["Persist Clean Entity in PostgreSQL<br/>Serve to Flutter Client & AI Recommender"]
```

---

## 5. Cambodian Company Normalization Rules

The normalization engine in [`backend/app/services/company_resolver.py`](file:///Users/microstore/android_studio_projects/YEAR_FOUR/PP/project-practicum-blueprint/backend/app/services/company_resolver.py) adheres to strict preservation rules:

### Normalization Operations:
1. **Lowercase conversion:** Standardizes case sensitivity.
2. **Emoji & Decorative stripping:** Removes recruitment noise (`🔥`, `⚡`, `📢`, `‼️`, `💼`).
3. **Punctuation normalization:** Collapses periods, commas, slashes, and dashes to single spaces.
4. **Country qualifier removal:** Strips non-distinguishing country qualifiers (`"(Cambodia)"`, `"Cambodia"`, `"Khmer"`).
5. **Corporate legal suffix removal:** Strips non-distinguishing corporate suffixes (`"co., ltd"`, `"plc"`, `"inc."`, `"corp."`, `"llc"`, `"ltd"`).
6. **Brand identity preservation (CRITICAL):** The engine **never** removes brand-defining keywords such as `"Bank"`, `"Group"`, `"Cement"`, `"Telecom"`, or `"Insurance"`. Removing `"Bank"` from `"ABA Bank"` would corrupt the legal identity.

### Real-World Cambodian Test Matrix:

| Raw Scraped String | Corporate Suffix Stripped | `normalized_name` | Canonical Entity |
|---|---|---|---|
| `🔥 URGENT ABA Bank Plc.` | `🔥 URGENT`, `Plc.` | `aba bank` | **ABA Bank** |
| `ABA Bank (Cambodia) Plc.` | `(Cambodia)`, `Plc.` | `aba bank` | **ABA Bank** |
| `Advanced Bank of Asia Ltd` | `Ltd` | `advanced bank of asia` | **ABA Bank** (Via Verified Alias) |
| `Smart Axiata Co., Ltd.` | `Co., Ltd.` | `smart axiata` | **Smart Axiata** |
| `Wing Bank (Cambodia) Plc` | `(Cambodia)`, `Plc` | `wing bank` | **Wing Bank** |
| `Chip Mong Insee Cement Corp.` | `Corp.` | `chip mong insee cement` | **Chip Mong Insee Cement** (Subsidiary) |

---

## 6. 4-Tier Resolution Algorithm & Safety Gate

To prevent false merges, the system processes incoming company names through 4 strict tiers:

### Tier 1: Exact Canonical Match ($O(\log n)$ B-Tree Index)
- Looks up `companies.normalized_name == norm_name`.
- If found, immediately returns canonical `company_id`.
- Enriches missing logo URL or website URL if provided by the new source.

### Tier 2: Verified Alias Lookup ($O(\log n)$)
- Queries `company_aliases.normalized_alias == norm_name`.
- If found AND `is_verified == True`, returns the associated `company_id`.

### Tier 3: Controlled Fuzzy Candidate Matching ($\ge 90\%$)
- Compares against active canonical companies using RapidFuzz `token_sort_ratio`.
- **Safety Gate:** A score $\ge 90\%$ **does not trigger an automatic merge**. It triggers a candidate evaluation:
  - If the recruiter's email domain matches the company's verified domain (`@ababank.com`), the match is accepted.
  - If evidence is conflicting or ambiguous, the match is rejected to prevent database corruption.

### Tier 4: New Canonical Ingestion & Confidential Handling
- If the employer is a recruitment agency posting on behalf of a confidential client: `company_id` is set to `NULL`.
- If evidence indicates a clear, new hiring organization: A new record is created in `companies` with:
  - `is_verified = False`
  - `verification_status = 'unverified'`
  - Clean URL-safe slug generated (e.g. `aba-bank`, `aba-bank-1`).

---

## 7. Integration with Job Deduplication Engine

Company resolution and job deduplication are strictly decoupled services:

```text
Raw Scrape ➔ Company Resolver (company_id) ➔ Job Normalizer ➔ Dedup Manager (dedup_hash) ➔ PostgreSQL
```

### Why Company Resolution Must Run First:
Consider two postings for the exact same job from different platforms:
- **Telegram:** Title: `"Junior Mobile Developer"`, Company: `"ABA Bank Plc."`
- **CamHR:** Title: `"Junior Mobile Developer"`, Company: `"Advanced Bank of Asia Ltd"`

If deduplication runs first using string equality, the two postings appear to belong to completely different companies. Deduplication fails, and duplicate cards appear on the mobile app.

By resolving the company first:
- Both jobs receive `company_id = 15`.
- The deduplication hash becomes:
  $$\text{dedup\_hash} = \text{SHA-256}(\text{"junior mobile developer"} \mid \mathbf{15} \mid \text{"phnom penh"})$$
- Both hashes match identically. The CamHR listing is soft-linked to the Telegram canonical job (`duplicate_of = telegram_id`), and missing fields (structured salary, deadline) are merged non-destructively.

---

## 8. FastAPI Endpoints & API Contract

The system exposes 4 public REST endpoints in [`backend/app/api/companies.py`](file:///Users/microstore/android_studio_projects/YEAR_FOUR/PP/project-practicum-blueprint/backend/app/api/companies.py):

| Method | Endpoint | Query / Path Parameters | Description |
|---|---|---|---|
| **GET** | `/api/v1/companies` | `q`, `industry`, `is_verified`, `limit`, `offset` | List companies with active job counts |
| **GET** | `/api/v1/companies/{id}` | `id` (int) | Retrieve full company profile with verified aliases |
| **GET** | `/api/v1/companies/{id}/jobs` | `id` (int), `limit`, `offset` | List active canonical jobs published by this company |
| **POST** | `/api/v1/companies/resolve` | `{"raw_name": "..."}` | Utility endpoint to resolve and test entity matching |

### Sample Response (`GET /api/v1/companies/{id}`):
```json
{
  "id": 15,
  "name": "ABA Bank",
  "normalized_name": "aba bank",
  "slug": "aba-bank",
  "logo_url": "https://cdn.jobmatch.com.kh/logos/aba.png",
  "website_url": "https://www.ababank.com",
  "industry": "Banking & Finance",
  "headquarters": "Phnom Penh",
  "description": "Advanced Bank of Asia Limited is one of Cambodia's premier commercial banks.",
  "is_verified": true,
  "verification_status": "verified",
  "active_jobs_count": 12,
  "aliases": [
    {
      "id": 101,
      "alias_name": "Advanced Bank of Asia Ltd",
      "normalized_alias": "advanced bank of asia",
      "is_verified": true
    },
    {
      "id": 102,
      "alias_name": "ABA Bank (Cambodia) Plc.",
      "normalized_alias": "aba bank",
      "is_verified": true
    }
  ]
}
```

---

## 9. Evaluation Metrics & Testing Strategy

The company resolution engine is verified through unit tests and empirical evaluation:

### 9.1 Unit Test Coverage (`test_company_resolver.py` & `test_companies_api.py`)
- **TC-C01:** Slug generation sanitizes punctuation and spaces (`"Smart Axiata Co., Ltd."` $\rightarrow$ `"smart-axiata-co-ltd"`).
- **TC-C02:** Suffix stripping normalizes legal terms while preserving brand keywords (`"ABA Bank (Cambodia) Plc."` $\rightarrow$ `"aba bank"`).
- **TC-C03:** Exact canonical matches return existing company without creating duplicates.
- **TC-C04:** Verified alias matches correctly map alternative legal names (`"Advanced Bank of Asia Ltd"` $\rightarrow$ `"ABA Bank"`).
- **TC-C05:** Incoming scraped jobs via `save_job_with_dedup` automatically link `job_listings.company_id`.
- **TC-C06:** Public API endpoints list companies, display active job counts, and return HTTP 404 for missing IDs.

### 9.2 Evaluation Metrics
- **Precision:** $\frac{TP}{TP + FP}$ — Target $\ge 99\%$. Ensures distinct legal entities are never incorrectly merged.
- **Recall:** $\frac{TP}{TP + FN}$ — Target $\ge 95\%$. Successfully resolves multi-platform naming variations.
- **False Merge Rate:** Target $< 0.5\%$. Strict corroborating evidence gate prevents accidental corporate merges.

---

## 10. Component & Codebase Traceability

| Architecture Component | Code File Path | Status |
|---|---|---|
| **`companies` Table** | `backend/app/models/models.py` | Migrated in PostgreSQL (Alembic `f6a7b8c9d0e1`) |
| **`company_aliases` Table** | `backend/app/models/models.py` | Migrated in PostgreSQL (Alembic `f6a7b8c9d0e1`) |
| **`job_listings.company_id`** | `backend/app/models/models.py` | Foreign key `ON DELETE SET NULL` active |
| **Normalization Engine** | `backend/app/services/company_resolver.py` | `normalize_company_name()` tested & active |
| **Resolution Service** | `backend/app/services/company_resolver.py` | `resolve_company()` 4-tier flow tested & active |
| **Pipeline Integration** | `backend/app/services/dedup_manager.py` | `save_job_with_dedup()` links canonical company |
| **Pydantic Schemas** | `backend/app/schemas/schemas.py` | `CompanyResponse`, `CompanyDetailResponse` |
| **FastAPI Endpoints** | `backend/app/api/companies.py` | Router included in `backend/main.py` |
| **Automated Tests** | `backend/tests/test_company_resolver.py` | **79/79 Backend Tests Passing (100%)** |
