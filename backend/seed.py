import os
from datetime import datetime, date
from app.core.database import SessionLocal, engine, Base
from app.models.models import Skill, JobListing, JobSkill, User, Profile
from app.core.security import hash_password

def seed_database():
    print("🌱 Connecting to database and creating tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Seed Skills Catalog
        skill_catalog = [
            ("Flutter", "Mobile"),
            ("Dart", "Mobile"),
            ("Python", "Backend"),
            ("FastAPI", "Backend"),
            ("PostgreSQL", "Database"),
            ("Git", "DevOps"),
            ("Docker", "DevOps"),
            ("UI/UX", "Design"),
            ("Figma", "Design"),
            ("React Native", "Mobile"),
            ("Java", "Backend"),
            ("JavaScript", "Frontend"),
            ("REST API", "Backend"),
            ("Data Scraping", "Data")
        ]

        print("✨ Seeding master skills catalog...")
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

        # 2. Seed a Test Candidate (Dara)
        test_email = "dara@example.com"
        existing_user = db.query(User).filter(User.email == test_email).first()
        if not existing_user:
            print("👤 Seeding test candidate user (dara@example.com)...")
            user = User(
                email=test_email,
                password_hash=hash_password("Password123!"),
                role="user"
            )
            db.add(user)
            db.flush()

            profile = Profile(
                user_id=user.id,
                full_name="Dara Sok",
                education="Computer Science, Year 4",
                experience_level="entry",
                preferred_role="Junior Flutter Developer",
                preferred_location="Phnom Penh",
                expected_salary=350.00
            )
            db.add(profile)
            db.flush()

        # Seed System Administrator
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

        # 3. Seed Sample Cambodian Job Listing
        sample_url = "https://t.me/internshipscambodia/sample_101"
        existing_job = db.query(JobListing).filter(JobListing.source_url == sample_url).first()
        if not existing_job:
            print("💼 Seeding sample job vacancy...")
            job = JobListing(
                title="Junior Flutter Developer",
                company="TechKhmer Solutions",
                location="Phnom Penh",
                experience_level="entry",
                job_type="full-time",
                salary_min=300.00,
                salary_max=500.00,
                salary_currency="USD",
                is_negotiable=True,
                description="Looking for an enthusiastic Junior Flutter Developer to join our mobile team in Phnom Penh. Experience with Flutter, Dart, REST API and Git required.",
                source="Telegram",
                source_url=sample_url,
                posted_at=date.today(),
                deadline=date(2026, 12, 31),
                is_active=True
            )
            db.add(job)
            db.flush()

            # Attach skills to job
            for skill_name in ["Flutter", "Dart", "Git", "REST API"]:
                if skill_name in skills_map:
                    db.add(JobSkill(job_id=job.id, skill_id=skills_map[skill_name].id))

        db.commit()
        print("✅ Database seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"❌ Seeding error: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
