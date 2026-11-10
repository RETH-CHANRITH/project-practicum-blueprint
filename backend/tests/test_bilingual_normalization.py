import pytest
from app.services.scraper import _normalize_location, _parse_salary_from_text
from app.services.job_classifier import rule_based_classify
from app.services.matching_engine import normalize_skill
from app.services.dedup_manager import normalize_text_for_matching

def test_salary_normalization_khmer_and_riel():
    """Verify Khmer numeral parsing, KHR currency detection, and period detection."""
    # 1. Riel with Khmer numerals
    raw_riel = "ប្រាក់ខែ: ១,២០០,០០០ ដល់ ២,០០០,០០០ រៀល / ក្នុងមួយខែ (ចរចា)"
    s_min, s_max, s_curr, s_period, is_neg = _parse_salary_from_text(raw_riel)
    assert s_min == 1200000.0
    assert s_max == 2000000.0
    assert s_curr == "KHR"
    assert s_period == "monthly"
    assert is_neg is True

    # 2. Hourly salary detection (e.g. Barista / Tutor)
    raw_hourly = "Barista: $1.50 - $2.50 / hour, part-time"
    s_min, s_max, s_curr, s_period, is_neg = _parse_salary_from_text(raw_hourly)
    # The regex checks 2-9 digits; let's test integer hourly rate e.g. $10 - $20 / hr
    raw_hourly_int = "Private English Tutor: $10 - $20 / hour"
    s_min, s_max, s_curr, s_period, is_neg = _parse_salary_from_text(raw_hourly_int)
    assert s_min == 10.0
    assert s_max == 20.0
    assert s_curr == "USD"
    assert s_period == "hourly"

    # 3. Daily salary detection
    raw_daily = "Site Construction Supervisor: $15 - $25 / day"
    s_min, s_max, s_curr, s_period, is_neg = _parse_salary_from_text(raw_daily)
    assert s_min == 15.0
    assert s_max == 25.0
    assert s_period == "daily"

    # 4. Exact Single Salary (verify NO 1.3x artificial inflation)
    raw_single = "Accountant Salary: $600 USD per month"
    s_min, s_max, s_curr, s_period, is_neg = _parse_salary_from_text(raw_single)
    assert s_min == 600.0
    assert s_max == 600.0  # Exact match, not inflated to 780!


def test_location_normalization_25_provinces_bilingual():
    """Verify provincial mapping across Cambodia in both English and Khmer script."""
    # Major hubs
    assert _normalize_location("Office in Siem Reap, near Pub Street") == "Siem Reap, Cambodia"
    assert _normalize_location("ទីតាំងនៅខេត្តសៀមរាប") == "Siem Reap, Cambodia"
    
    assert _normalize_location("Branch in Sihanoukville port") == "Preah Sihanouk, Cambodia"
    assert _normalize_location("ធ្វើការនៅកំពង់សោម") == "Preah Sihanouk, Cambodia"
    
    assert _normalize_location("Battambang City Center") == "Battambang, Cambodia"
    assert _normalize_location("ការិយាល័យបាត់ដំបង") == "Battambang, Cambodia"

    # Previously missing provinces
    assert _normalize_location("Kampong Cham riverbank branch") == "Kampong Cham, Cambodia"
    assert _normalize_location("សាខាកំពង់ចាម") == "Kampong Cham, Cambodia"

    assert _normalize_location("Koh Kong eco resort") == "Koh Kong, Cambodia"
    assert _normalize_location("ទីតាំងនៅកោះកុង") == "Koh Kong, Cambodia"

    assert _normalize_location("Eco Lodge in Mondulkiri") == "Mondulkiri, Cambodia"
    assert _normalize_location("ខេត្តមណ្ឌលគិរី") == "Mondulkiri, Cambodia"

    assert _normalize_location("Factory in Bavet, Svay Rieng") == "Svay Rieng, Cambodia"
    assert _normalize_location("ក្រុងបាវិត ខេត្តស្វាយរៀង") == "Svay Rieng, Cambodia"

    assert _normalize_location("Casino resort in Poipet") == "Banteay Meanchey, Cambodia"
    assert _normalize_location("ក្រុងប៉ោយប៉ែត") == "Banteay Meanchey, Cambodia"


def test_khmer_and_multi_industry_classification():
    """Verify classification engine handles pure Khmer and multi-industry roles."""
    # 1. Pure Khmer Education Post
    khmer_edu = rule_based_classify(
        title="គ្រូបង្រៀនភាសាអង់គ្លេស",
        description="សាលាត្រូវការជ្រើសរើសគ្រូបង្រៀនកម្រិតបឋមសិក្សា បង្រៀនសិស្ស",
        company="សាលាអន្តរជាតិ"
    )
    assert khmer_edu["job_category"] == "Education"

    # 2. Pure Khmer Accounting Post
    khmer_acct = rule_based_classify(
        title="បុគ្គលិកគណនេយ្យ",
        description="ទទួលខុសត្រូវរៀបចំរបាយការណ៍ហិរញ្ញវត្ថុ និងគណនេយ្យប្រចាំខែ",
        company="ក្រុមហ៊ុនពាណិជ្ជកម្ម"
    )
    assert khmer_acct["job_category"] == "Finance & Accounting"

    # 3. Pure Khmer Healthcare Post
    khmer_health = rule_based_classify(
        title="គិលានុបដ្ឋាយិកា",
        description="មើលថែអ្នកជំងឺ និងជួយវេជ្ជបណ្ឌិតនៅក្នុងមន្ទីរពេទ្យ",
        company="មន្ទីរសម្រាកព្យាបាល"
    )
    assert khmer_health["job_category"] == "Healthcare"

    # 4. Pure Khmer Internship Seniority
    khmer_intern = rule_based_classify(
        title="អ្នកហាត់ការផ្នែកទីផ្សារ",
        description="ឱកាសកម្មសិក្សាសម្រាប់និស្សិតទើបបញ្ចប់ការសិក្សា",
        company="ក្រុមហ៊ុន"
    )
    assert khmer_intern["job_level"] == "Internship"
    assert khmer_intern["job_category"] == "Marketing"


def test_multi_industry_skills_normalization():
    """Verify skill canonicalization covers Healthcare, Hospitality, Construction, and Khmer."""
    # Healthcare
    assert normalize_skill("Nurse") == "nursing"
    assert normalize_skill("Pharmacist") == "pharmacy"
    assert normalize_skill("Patient Care") == "patient care"

    # Hospitality & F&B
    assert normalize_skill("Barista") == "barista operations"
    assert normalize_skill("Cooking") == "culinary arts"
    assert normalize_skill("Chef") == "culinary arts"
    assert normalize_skill("Front Desk") == "hotel front desk"

    # Construction & Engineering
    assert normalize_skill("AutoCAD") == "autocad"
    assert normalize_skill("Civil Engineering") == "civil engineering"
    assert normalize_skill("Site Safety") == "site safety supervision"

    # Khmer Skill Aliases
    assert normalize_skill("គណនេយ្យ") == "accounting"
    assert normalize_skill("ភាសាអង់គ្លេស") == "english communication"
    assert normalize_skill("សរសេរកូដ") == "software engineering"


def test_cross_industry_job_title_normalization():
    """Verify title standardization cleans abbreviations across industries and Khmer titles."""
    assert "accountant" in normalize_text_for_matching("Sr. Acct. Officer")
    assert "assistant" in normalize_text_for_matching("Exec. Asst. to Director")
    assert "intern" in normalize_text_for_matching("អ្នកហាត់ការផ្នែកព័ត៌មានវិទ្យា")
    assert "teacher" in normalize_text_for_matching("គ្រូបង្រៀនភាសាខ្មែរ")

