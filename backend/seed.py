import os
from datetime import datetime, date
from app.core.database import SessionLocal, engine, Base
from app.models.models import Skill, JobListing, JobSkill, User, Profile, ProfileSkill, Source, Company
from app.core.security import hash_password
from app.services.company_resolver import resolve_company

def seed_database():
    print("🌱 Connecting to database and creating tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Master Skills Catalog (Multi-Industry: Tech, Banking, Finance, Marketing, HR, Sales, Languages)
        skill_catalog = [
            # Mobile & Software Engineering
            ("Flutter", "Mobile"),
            ("Dart", "Mobile"),
            ("React Native", "Mobile"),
            ("Python", "Backend"),
            ("FastAPI", "Backend"),
            ("Java", "Backend"),
            ("JavaScript", "Frontend"),
            ("REST API", "Backend"),
            ("PostgreSQL", "Database"),
            ("Git", "DevOps"),
            ("Docker", "DevOps"),
            ("Cybersecurity", "Security"),
            ("IT Support", "IT Support"),
            ("Data Scraping", "Data"),

            # Design & Creative
            ("UI/UX", "Design"),
            ("Figma", "Design"),
            ("Graphic Design", "Design"),
            ("Adobe Photoshop", "Design"),
            ("Adobe Illustrator", "Design"),

            # Finance & Accounting
            ("Accounting", "Finance & Accounting"),
            ("Tax Compliance", "Finance & Accounting"),
            ("Financial Reporting", "Finance & Accounting"),
            ("Financial Analysis", "Finance & Accounting"),
            ("QuickBooks", "Finance & Accounting"),
            ("Auditing", "Finance & Accounting"),

            # Banking & Microfinance
            ("Credit Analysis", "Banking"),
            ("Loan Processing", "Banking"),
            ("Teller Operations", "Banking"),
            ("KYC Compliance", "Banking"),
            ("Risk Assessment", "Banking"),

            # Marketing & Digital Media
            ("Digital Marketing", "Marketing"),
            ("Social Media Management", "Marketing"),
            ("Content Marketing", "Marketing"),
            ("SEO", "Marketing"),
            ("Copywriting", "Marketing"),
            ("Brand Strategy", "Marketing"),

            # Sales & Business Development
            ("B2B Sales", "Sales"),
            ("Business Development", "Sales"),
            ("Lead Generation", "Sales"),
            ("Negotiation", "Sales"),
            ("CRM", "Sales"),

            # Human Resources & Administration
            ("Recruitment", "Human Resources"),
            ("Labor Law Compliance", "Human Resources"),
            ("Payroll Management", "Human Resources"),
            ("Office Administration", "Administration"),

            # Professional & Languages
            ("English Communication", "Language"),
            ("Khmer Communication", "Language"),
            ("Microsoft Excel", "Productivity"),
            ("Customer Service", "Customer Service"),
        ]

        print("✨ Seeding master multi-industry skills catalog...")
        skills_map = {}
        for name, category in skill_catalog:
            existing = db.query(Skill).filter(Skill.name == name).first()
            if not existing:
                skill = Skill(name=name, category=category)
                db.add(skill)
                db.flush()
                skills_map[name] = skill
            else:
                skills_map[name] = existing

        # 2. Seed Master Aggregation Sources (10 Cambodian Portals & Telegram Channels)
        sources_catalog = [
            {
                "name": "Internships Cambodia",
                "code": "internships_cambodia",
                "platform_type": "telegram",
                "url": "https://t.me/internshipscambodia",
                "logo_url": "assets/icons/telegram.png",
                "is_active": True,
                "scrape_interval_minutes": 60,
            },
            {
                "name": "BongThom",
                "code": "bongthom",
                "platform_type": "web_portal",
                "url": "https://www.bongthom.com",
                "logo_url": "assets/icons/bongthom.png",
                "is_active": True,
                "scrape_interval_minutes": 120,
            },
            {
                "name": "BongThom Telegram",
                "code": "bongthom_telegram",
                "platform_type": "telegram",
                "url": "https://t.me/BongThomCom",
                "logo_url": "assets/icons/telegram.png",
                "is_active": True,
                "scrape_interval_minutes": 60,
            },
            {
                "name": "JobNet Cambodia",
                "code": "jobnet",
                "platform_type": "web_portal",
                "url": "https://www.jobnet.com.kh",
                "logo_url": "assets/icons/jobnet.png",
                "is_active": True,
                "scrape_interval_minutes": 120,
            },
            {
                "name": "Khmer24 Jobs",
                "code": "khmer24",
                "platform_type": "web_portal",
                "url": "https://www.khmer24.com/en/jobs/",
                "logo_url": "assets/icons/khmer24.png",
                "is_active": True,
                "scrape_interval_minutes": 120,
            },
            {
                "name": "Workingna Telegram",
                "code": "workingna_telegram",
                "platform_type": "telegram",
                "url": "https://t.me/workingnajob",
                "logo_url": "assets/icons/telegram.png",
                "is_active": True,
                "scrape_interval_minutes": 60,
            },
            {
                "name": "CamboJob Careers Telegram",
                "code": "cambojob_telegram",
                "platform_type": "telegram",
                "url": "https://t.me/CBjobopportunity",
                "logo_url": "assets/icons/telegram.png",
                "is_active": True,
                "scrape_interval_minutes": 60,
            },
            {
                "name": "Asean-Works",
                "code": "asean_works",
                "platform_type": "web_portal",
                "url": "https://asean-works.com",
                "logo_url": "assets/icons/aseanworks.png",
                "is_active": False,
                "scrape_interval_minutes": 120,
            },
            {
                "name": "Workingna",
                "code": "workingna",
                "platform_type": "web_portal",
                "url": "https://www.workingna.com",
                "logo_url": "assets/icons/workingna.png",
                "is_active": False,
                "scrape_interval_minutes": 120,
            },
            {
                "name": "CamboJob",
                "code": "cambojob",
                "platform_type": "web_portal",
                "url": "https://www.cambojob.com",
                "logo_url": "assets/icons/cambojob.png",
                "is_active": False,
                "scrape_interval_minutes": 120,
            },
        ]

        print("📡 Seeding master aggregation sources...")
        sources_map = {}
        for s_data in sources_catalog:
            existing_s = db.query(Source).filter(Source.code == s_data["code"]).first()
            if not existing_s:
                s_obj = Source(**s_data)
                db.add(s_obj)
                db.flush()
                sources_map[s_data["code"]] = s_obj
            else:
                existing_s.is_active = s_data["is_active"]
                sources_map[s_data["code"]] = existing_s

        # 3. Seed Diverse Candidates (Entry, Mid, Senior Across Industries)
        candidates_data = [
            {
                "email": "dara@example.com",
                "full_name": "Dara Sok",
                "education": "Computer Science, Year 4 (RUPP)",
                "experience_level": "entry",
                "preferred_role": "Junior Flutter Developer",
                "preferred_location": "Phnom Penh",
                "expected_salary": 350.00,
                "skills": ["Flutter", "Dart", "Git", "REST API"],
            },
            {
                "email": "sreymom@example.com",
                "full_name": "Sreymom Pich",
                "education": "BA in Media & Communications (DMC)",
                "experience_level": "mid",
                "preferred_role": "Digital Marketing Specialist",
                "preferred_location": "Phnom Penh",
                "expected_salary": 650.00,
                "skills": ["Digital Marketing", "Social Media Management", "Content Marketing", "Graphic Design", "English Communication", "Khmer Communication"],
            },
            {
                "email": "bopha@example.com",
                "full_name": "Bopha Chea",
                "education": "Bachelor of Banking & Finance (NUM)",
                "experience_level": "senior",
                "preferred_role": "Senior Accountant / Credit Specialist",
                "preferred_location": "Phnom Penh",
                "expected_salary": 950.00,
                "skills": ["Accounting", "Financial Reporting", "Credit Analysis", "Tax Compliance", "Microsoft Excel", "Risk Assessment"],
            },
        ]

        print("👤 Seeding multi-industry candidates...")
        for c in candidates_data:
            user = db.query(User).filter(User.email == c["email"]).first()
            if not user:
                user = User(
                    email=c["email"],
                    password_hash=hash_password("Password123!"),
                    role="user"
                )
                db.add(user)
                db.flush()

                profile = Profile(
                    user_id=user.id,
                    full_name=c["full_name"],
                    education=c["education"],
                    experience_level=c["experience_level"],
                    preferred_role=c["preferred_role"],
                    preferred_location=c["preferred_location"],
                    expected_salary=c["expected_salary"],
                )
                db.add(profile)
                db.flush()

                for s_name in c["skills"]:
                    if s_name in skills_map:
                        db.add(ProfileSkill(profile_id=profile.id, skill_id=skills_map[s_name].id))

        # Seed System Administrator (Strictly 2-role system: user & admin)
        admin_email = "admin@jobmatch.com"
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if not existing_admin:
            print("🛡️ Seeding system administrator (admin@jobmatch.com)...")
            admin_user = User(
                email=admin_email,
                password_hash=hash_password("AdminPassword123!"),
                role="admin"
            )
            db.add(admin_user)
            db.flush()

        # 4. Seed Multi-Industry Cambodian Job Listings
        jobs_data = [
            {
                "source_code": "internships_cambodia",
                "source_name": "Telegram",
                "source_url": "https://t.me/internshipscambodia/sample_101",
                "company_name": "TechKhmer Solutions",
                "title": "Junior Flutter Developer",
                "location": "Phnom Penh",
                "job_category": "Information Technology",
                "job_subcategory": "Mobile Development",
                "job_level": "Junior",
                "experience_level": "entry",
                "job_type": "full_time",
                "work_arrangement": "on-site",
                "salary_min": 300.00,
                "salary_max": 500.00,
                "description": "Looking for an enthusiastic Junior Flutter Developer to join our mobile team in Phnom Penh. Experience with Flutter, Dart, REST API and Git required.",
                "skills": ["Flutter", "Dart", "Git", "REST API"],
            },
            {
                "source_code": "bongthom_telegram",
                "source_name": "Telegram",
                "source_url": "https://t.me/BongThomCom/sample_201",
                "company_name": "ABA Bank",
                "title": "Credit Officer",
                "location": "Phnom Penh",
                "job_category": "Banking",
                "job_subcategory": "Commercial Banking",
                "job_level": "Junior",
                "experience_level": "junior",
                "job_type": "full_time",
                "work_arrangement": "on-site",
                "salary_min": 350.00,
                "salary_max": 600.00,
                "description": "ABA Bank is seeking a dedicated Credit Officer to assess loan applications, analyze borrower creditworthiness, ensure KYC compliance, and deliver exceptional customer service across our branches.",
                "skills": ["Credit Analysis", "Loan Processing", "KYC Compliance", "Customer Service", "Khmer Communication"],
            },
            {
                "source_code": "bongthom",
                "source_name": "BongThom",
                "source_url": "https://www.bongthom.com/job_detail/sample_301",
                "company_name": "Chip Mong Group",
                "title": "Senior Accountant",
                "location": "Phnom Penh",
                "job_category": "Finance & Accounting",
                "job_subcategory": "Corporate Accounting",
                "job_level": "Senior",
                "experience_level": "senior",
                "job_type": "full_time",
                "work_arrangement": "on-site",
                "salary_min": 800.00,
                "salary_max": 1400.00,
                "description": "Chip Mong Group is looking for an experienced Senior Accountant to lead monthly financial reporting, tax compliance audits, balance sheet reconciliations, and financial analysis using Microsoft Excel and accounting systems.",
                "skills": ["Accounting", "Financial Reporting", "Tax Compliance", "Auditing", "Microsoft Excel"],
            },
            {
                "source_code": "jobnet",
                "source_name": "JobNet",
                "source_url": "https://www.jobnet.com.kh/jobs/sample_401",
                "company_name": "Smart Axiata",
                "title": "Digital Marketing Specialist",
                "location": "Phnom Penh",
                "job_category": "Marketing",
                "job_subcategory": "Digital Media",
                "job_level": "Mid-level",
                "experience_level": "mid",
                "job_type": "full_time",
                "work_arrangement": "hybrid",
                "salary_min": 500.00,
                "salary_max": 900.00,
                "description": "Smart Axiata is hiring a Digital Marketing Specialist to manage social media campaigns, content marketing strategies, SEO optimization, brand communications, and creative visual assets.",
                "skills": ["Digital Marketing", "Social Media Management", "Content Marketing", "SEO", "Graphic Design", "English Communication"],
            },
            {
                "source_code": "workingna_telegram",
                "source_name": "Telegram",
                "source_url": "https://t.me/workingnajob/sample_501",
                "company_name": "CP Cambodia",
                "title": "HR & Recruitment Officer",
                "location": "Phnom Penh",
                "job_category": "Human Resources",
                "job_subcategory": "Talent Acquisition",
                "job_level": "Junior",
                "experience_level": "junior",
                "job_type": "full_time",
                "work_arrangement": "on-site",
                "salary_min": 400.00,
                "salary_max": 700.00,
                "description": "CP Cambodia is seeking an HR & Recruitment Officer responsible for managing end-to-end talent acquisition, labor law compliance, onboarding processes, payroll administration, and employee records.",
                "skills": ["Recruitment", "Labor Law Compliance", "Office Administration", "Payroll Management", "Khmer Communication"],
            },
            {
                "source_code": "cambojob_telegram",
                "source_name": "Telegram",
                "source_url": "https://t.me/CBjobopportunity/sample_601",
                "company_name": "TotalEnergies Cambodia",
                "title": "B2B Sales Executive",
                "location": "Phnom Penh",
                "job_category": "Sales",
                "job_subcategory": "Corporate Sales",
                "job_level": "Mid-level",
                "experience_level": "mid",
                "job_type": "full_time",
                "work_arrangement": "on-site",
                "salary_min": 600.00,
                "salary_max": 1100.00,
                "description": "TotalEnergies Marketing (Cambodia) is seeking a motivated B2B Sales Executive to identify commercial prospects, negotiate corporate supply agreements, conduct lead generation, and build sustainable client relationships.",
                "skills": ["B2B Sales", "Business Development", "Negotiation", "Lead Generation", "English Communication"],
            },
        ]

        print("💼 Seeding multi-industry Cambodian job vacancies...")
        for j_data in jobs_data:
            existing_job = db.query(JobListing).filter(JobListing.source_url == j_data["source_url"]).first()
            if not existing_job:
                source_obj = sources_map.get(j_data["source_code"])
                comp_entity, _ = resolve_company(db, j_data["company_name"], auto_create=True)
                
                job = JobListing(
                    source_id=source_obj.id if source_obj else None,
                    company_id=comp_entity.id if comp_entity else None,
                    title=j_data["title"],
                    company=j_data["company_name"],
                    location=j_data["location"],
                    normalized_location=j_data["location"],
                    experience_level=j_data["experience_level"],
                    job_type=j_data["job_type"],
                    work_arrangement=j_data["work_arrangement"],
                    job_category=j_data["job_category"],
                    job_subcategory=j_data["job_subcategory"],
                    job_level=j_data["job_level"],
                    classification_confidence=0.95,
                    classification_source="rule",
                    salary_min=j_data["salary_min"],
                    salary_max=j_data["salary_max"],
                    salary_currency="USD",
                    salary_period="monthly",
                    is_negotiable=True,
                    description=j_data["description"],
                    source=j_data["source_name"],
                    source_url=j_data["source_url"],
                    posted_at=date.today(),
                    deadline=date(2026, 12, 31),
                    is_active=True
                )
                db.add(job)
                db.flush()

                # Attach skills to job
                for s_name in j_data["skills"]:
                    if s_name in skills_map:
                        db.add(JobSkill(job_id=job.id, skill_id=skills_map[s_name].id))

        db.commit()
        print("✅ Multi-industry database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Seeding error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
