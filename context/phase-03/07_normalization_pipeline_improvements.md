# Phase 3.7 — Data Normalization Pipeline: Technical Audit, Implemented Enhancements & Future Roadmap

**Document Type:** Formal Capstone Engineering Review & Enhancement Record  
**Project:** JobMatch Cambodia — AI-Assisted Multi-Source Job Aggregator  
**Academic Program:** Bachelor of Computer Science — Individual Capstone Project  
**Author:** RETH CHAN RITH (Student E2)  
**Academic Advisor:** Sopheak  
**Status:** Implemented & Verified · **Last Updated:** 2026-11-09  

---

## 1. System Scope & Ingestion Architecture

JobMatch Cambodia is an **external job vacancy aggregator and AI recommendation engine**.
- **Data Provenance:** Aggregates public vacancies exclusively from external platforms (Telegram recruitment channels, Cambodian job portals, and web crawlers).
- **Zero Employer Portal:** Employers do **not** register, log in, or post jobs directly.
- **Strict Two-Role System:** Enforces strictly two roles: `user` (candidate) and `admin` (pipeline monitor).
- **External Applications:** Candidates apply via external source URLs, direct HR emails, phone numbers, or Telegram handles.

```
External Websites / Telegram Channels
                  │
                  ▼
          Job Scraping Engine
      (Telethon MTProto / BeautifulSoup)
                  │
                  ▼
          Raw Staging Layer
       (telegram_jobs / web_jobs)
                  │
                  ▼
          Data Sanitization
    (Emoji removal, regex cleanup,
      Khmer digit translation ០-៩)
                  │
                  ▼
          Data Normalization
    (25-province bilingual mapping,
    USD/KHR currencies, hourly/daily/monthly)
                  │
                  ▼
       4-Tier Company Resolution
    (Canonical 3NF Entity + Aliases)
                  │
                  ▼
        Master Skill Mapping
    (Multi-industry bilingual catalog)
                  │
                  ▼
      Hybrid Job Classification
    (TypeSafe AI Jev + Khmer Rule Engine)
                  │
                  ▼
       3-Tier Deduplication Engine
     (SHA-256 + Contact + RapidFuzz)
                  │
                  ▼
         PostgreSQL Database
    (job_listings, companies, skills)
                  │
                  ▼
       Dual-Metric AI Matching
    (70% Skill Coverage + 30% Semantic)
                  │
                  ▼
       Flutter Mobile Client App
```

---

## 2. Implemented Normalization Enhancements

### 2.1 Salary Normalization (`backend/app/services/scraper.py`)
- **Khmer Numeral Translation:** Full translation table `str.maketrans("០១២៣៤៥៦៧៨៩", "0123456789")` with comma stripping (`១,២០០,០០០` $\rightarrow$ `1200000`).
- **Dual-Currency Support:** Detects both **USD** (`$`, `usd`, `ដុល្លារ`) and **Cambodian Riel** (`៛`, `រៀល`, `khr`).
- **Payment Period Detection:** Identifies `hourly` (`/hr`, `/hour`, `ក្នុងមួយម៉ោង`, `ម៉ោង`), `daily` (`/day`, `ក្នុងមួយថ្ងៃ`, `ថ្ងៃ`), `monthly` (`/month`, `ក្នុងមួយខែ`), and `yearly`.
- **Exact Salary Preservation:** Removed artificial 1.3x single-salary inflation multiplier. A single advertised salary (e.g. `$600`) preserves `salary_min = 600.0` and `salary_max = 600.0`.
- **Negotiable Detection:** Accurately parses `negotiable`, `competitive`, and Khmer `ចរចា`.

### 2.2 Kingdom-Wide 25-Province Bilingual Normalization
- Complete lookup dictionary covering all **25 Cambodian provinces and capital** in both English and Khmer script:
  - Phnom Penh (`ភ្នំពេញ`, `pp`), Siem Reap (`សៀមរាប`, `sr`), Preah Sihanouk (`ព្រះសីហនុ`, `កំពង់សោម`), Battambang (`បាត់ដំបង`), Kandal (`កណ្តាល`), Banteay Meanchey (`បន្ទាយមានជ័យ`, `ប៉ោយប៉ែត`), Kampong Cham (`កំពង់ចាម`), Kampong Chhnang (`កំពង់ឆ្នាំង`), Kampong Speu (`កំពង់ស្ពឺ`), Kampong Thom (`កំពង់ធំ`), Kampot (`កំពត`), Kep (`កែប`), Koh Kong (`កោះកុង`), Kratie (`ក្រចេះ`), Mondulkiri (`មណ្ឌលគិរី`), Oddar Meanchey (`ឧត្តរមានជ័យ`), Pailin (`ប៉ៃលិន`), Preah Vihear (`ព្រះវិហារ`), Prey Veng (`ព្រៃវែង`), Pursat (`ពោធិ៍សាត់`), Ratanakiri (`រតនគិរី`), Stung Treng (`ស្ទឹងត្រែង`), Svay Rieng (`ស្វាយរៀង`, `បាវិត`), Takeo (`តាកែវ`), Tboung Khmum (`ត្បូងឃ្មុំ`).
- Handles unspaced Khmer script substrings accurately alongside English abbreviations.

### 2.3 Cross-Industry Bilingual Job Classification (`backend/app/services/job_classifier.py`)
- Rule-based fallback classifier upgraded with extensive Khmer vocabulary:
  - **Information Technology:** `អ្នកសរសេរកម្មវិធី`, `ព័ត៌មានវិទ្យា`, `អភិវឌ្ឍន៍`
  - **Finance & Accounting:** `គណនេយ្យ`, `គណនេយ្យករ`, `ហិរញ្ញវត្ថុ`, `សវនកម្ម`, `ពន្ធដារ`
  - **Banking & MFI:** `ធនាគារ`, `ឥណទាន`, `មន្ត្រីឥណទាន`, `បេឡា`, `មីក្រូហិរញ្ញវត្ថុ`
  - **Marketing:** `ទីផ្សារ`, `ផ្សព្វផ្សាយ`, `ប្រព័ន្ធផ្សព្វផ្សាយ`
  - **Sales:** `លក់`, `បុគ្គលិកលក់`, `ផ្នែកលក់`
  - **Human Resources:** `ធនធានមនុស្ស`, `ជ្រើសរើសបុគ្គលិក`, `ប្រាក់បៀវត្ស`
  - **Administration:** `រដ្ឋបាល`, `ស្មៀន`, `ទទួលភ្ញៀវ`
  - **Education:** `គ្រូបង្រៀន`, `បង្រៀន`, `សាស្ត្រាចារ្យ`, `អប់រំ`
  - **Hospitality & Tourism:** `សណ្ឋាគារ`, `ទេសចរណ៍`, `មេចុងភៅ`, `ភោជនីយដ្ឋាន`, `រត់តុ`
  - **Healthcare:** `ពេទ្យ`, `វេជ្ជបណ្ឌិត`, `គិលានុបដ្ឋាយិកា`, `ឱសថការី`, `សុខាភិបាល`
  - **Engineering & Construction:** `វិស្វករ`, `ស្ថាបត្យករ`, `សំណង់`
  - **Logistics:** `ឃ្លាំង`, `ដឹកជញ្ជូន`, `ស្តុក`
- Seniority levels in Khmer: `អ្នកហាត់ការ` / `កម្មសិក្សា` (Internship), `ទើបបញ្ចប់ការសិក្សា` (Entry-level), `កម្រិតដំបូង` (Junior), `ចាស់ទុំ` (Senior), `អ្នកគ្រប់គ្រង` (Manager), `នាយក` (Director).

### 2.4 Multi-Industry Skills Catalog (`backend/app/services/matching_engine.py`)
- Expanded `SKILL_ALIASES` to support:
  - **Healthcare:** Nursing, Pharmacy, Patient Care, Medical Laboratory, Clinical Diagnosis.
  - **Hospitality & Tourism:** Barista Operations, Culinary Arts, Food Safety Compliance, Hotel Front Desk, Housekeeping, Tour Guiding.
  - **Construction & Engineering:** AutoCAD, Civil Engineering, Surveying, Structural Design, Site Safety, HVAC, Electrical Wiring.
  - **Manufacturing & Garments:** Quality Control (AQL), Pattern Making, Industrial Sewing, Textile Inspection.
  - **Education:** Teaching, Lesson Planning, Curriculum Development, Classroom Management.
  - **Khmer Skill Aliases:** `គណនេយ្យ` $\rightarrow$ `accounting`, `ភាសាអង់គ្លេស` $\rightarrow$ `english communication`, `សរសេរកូដ` $\rightarrow$ `software engineering`, `បង្រៀន` $\rightarrow$ `teaching`.

### 2.5 Ingestion Pipeline Unification (`scraper.py` & `dedup_manager.py`)
- Connected `classify_job()` into both `scrape_and_ingest_telegram` and `scrape_and_ingest_web_url`.
- Scraped jobs are classified automatically before passing to `save_job_with_dedup`.
- `save_job_with_dedup` and `merge_into_main_job` explicitly persist `job_category`, `job_subcategory`, `job_level`, `classification_confidence`, `salary_currency`, and `salary_period`.

---

## 3. Verification & Automated Test Evidence

Automated test suite: [`backend/tests/test_bilingual_normalization.py`](file:///Users/microstore/android_studio_projects/YEAR_FOUR/PP/project-practicum-blueprint/backend/tests/test_bilingual_normalization.py)
* **`test_salary_normalization_khmer_and_riel`:** PASSED (Verified Riel, hourly, daily, exact single salary).
* **`test_location_normalization_25_provinces_bilingual`:** PASSED (Verified all 25 provinces in Khmer and English).
* **`test_khmer_and_multi_industry_classification`:** PASSED (Verified Education, Accounting, Healthcare, Internship in Khmer).
* **`test_multi_industry_skills_normalization`:** PASSED (Verified Healthcare, Hospitality, Construction, Khmer aliases).
* **`test_cross_industry_job_title_normalization`:** PASSED (Verified title abbreviations across industries and Khmer titles).

**Full Backend Test Suite:** **88 passed out of 88 (100%) in 33.36s.**

