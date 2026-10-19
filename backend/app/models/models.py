from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Numeric, Date, DateTime, ForeignKey, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    saved_jobs = relationship("SavedJob", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    education = Column(String(150), nullable=True)
    experience_level = Column(String(50), default="entry", nullable=False)
    preferred_role = Column(String(100), nullable=False)
    preferred_location = Column(String(100), default="Phnom Penh", nullable=False)
    expected_salary = Column(Numeric(10, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="profile")
    skills = relationship("ProfileSkill", back_populates="profile", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    category = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile_skills = relationship("ProfileSkill", back_populates="skill", cascade="all, delete-orphan")
    job_skills = relationship("JobSkill", back_populates="skill", cascade="all, delete-orphan")


class ProfileSkill(Base):
    __tablename__ = "profile_skills"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    profile = relationship("Profile", back_populates="skills")
    skill = relationship("Skill", back_populates="profile_skills")


class JobListing(Base):
    __tablename__ = "job_listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    location = Column(String(255), default="Phnom Penh", nullable=False)
    experience_level = Column(String(50), default="entry", nullable=False)
    job_type = Column(String(50), default="full-time", nullable=False)
    salary_min = Column(Numeric(10, 2), nullable=True)
    salary_max = Column(Numeric(10, 2), nullable=True)
    salary_currency = Column(String(10), default="USD", nullable=False)
    is_negotiable = Column(Boolean, default=False, nullable=False)
    description = Column(Text, nullable=False)
    source = Column(String(50), nullable=False)
    source_url = Column(Text, unique=True, nullable=False)
    posted_at = Column(Date, nullable=True)
    deadline = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    saved_by = relationship("SavedJob", back_populates="job", cascade="all, delete-orphan")


class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = Column(Integer, ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    job = relationship("JobListing", back_populates="skills")
    skill = relationship("Skill", back_populates="job_skills")


class SavedJob(Base):
    __tablename__ = "saved_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="saved_jobs")
    job = relationship("JobListing", back_populates="saved_by")
