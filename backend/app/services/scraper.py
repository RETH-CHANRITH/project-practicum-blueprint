import urllib.request
import re
from datetime import datetime
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.models.models import JobListing, Skill, JobSkill

def extract_channel_username(input_val: str) -> str:
    """Extract clean username whether user passes a channel name, @handle, or full t.me URL"""
    cleaned = input_val.strip()
    if "t.me/" in cleaned:
        cleaned = re.sub(r'https?://t\.me/(s/)?', '', cleaned)
    cleaned = cleaned.lstrip('@')
    return cleaned.split('/')[0].split('?')[0]

def scrape_and_ingest_telegram(db: Session, channel_or_url: str = "internshipscambodia") -> dict:
    """
    Scrapes live vacancies from public Telegram channel or URL preview
    and ingests them into the PostgreSQL database.
    """
    channel_username = extract_channel_username(channel_or_url)
    url = f"https://t.me/s/{channel_username}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')

    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.find_all('div', class_='tgme_widget_message_wrap')

    # Load master skills catalog for keyword extraction
    all_skills = db.query(Skill).all()

    new_jobs_count = 0

    for msg in messages:
        text_elem = msg.find('div', class_='tgme_widget_message_text')
        if not text_elem:
            continue
        text = text_elem.get_text(separator="\n").strip()

        link_elem = msg.find('a', class_='tgme_widget_message_date')
        post_url = link_elem['href'] if link_elem and 'href' in link_elem.attrs else ""
        if not post_url:
            continue

        # Check if already ingested (deduplication)
        existing = db.query(JobListing).filter(JobListing.source_url == post_url).first()
        if existing:
            continue

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < 2 or len(text) < 40:
            continue

        # Extract title and company heuristically
        raw_title = lines[0].replace("[", "").replace("]", "").strip()
        if len(raw_title) < 5 and len(lines) > 1:
            title = lines[1][:100]
        else:
            title = raw_title[:100]

        # Extract company name if available
        company = "Cambodia Hiring Organization"
        for line in lines[:5]:
            if "looking for" in line.lower() or "is seeking" in line.lower() or "co., ltd" in line.lower():
                company = line[:100]
                break

        # Extract posted date
        date_elem = msg.find('time')
        posted_date = None
        if date_elem and 'datetime' in date_elem.attrs:
            try:
                posted_date = datetime.fromisoformat(date_elem['datetime'].replace("Z", "+00:00")).date()
            except Exception:
                posted_date = datetime.utcnow().date()

        # Create new JobListing in PostgreSQL
        job = JobListing(
            title=title,
            company=company,
            location="Phnom Penh",
            experience_level="entry",
            job_type="internship" if "intern" in text.lower() else "full-time",
            salary_currency="USD",
            is_negotiable=True,
            description=text,
            source="Telegram",
            source_url=post_url,
            posted_at=posted_date,
            is_active=True
        )
        db.add(job)
        db.flush()

        # Extract matching skills from the job description text
        text_lower = text.lower()
        for skill in all_skills:
            # Word boundary matching so 'c' does not match 'candidate'
            pattern = r'\b' + re.escape(skill.name.lower()) + r'\b'
            if re.search(pattern, text_lower):
                db.add(JobSkill(job_id=job.id, skill_id=skill.id))

        new_jobs_count += 1

    db.commit()
    total_jobs = db.query(JobListing).count()

    return {
        "status": "success",
        "channel": f"@{channel_username}",
        "new_jobs_added": new_jobs_count,
        "total_jobs": total_jobs
    }
