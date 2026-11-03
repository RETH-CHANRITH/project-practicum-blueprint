"""add_companies_and_company_aliases

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-04 12:00:00.000000

Adds canonical companies and company_aliases tables (3NF Entity Resolution).
Links job_listings.company_id -> companies.id.
All changes are backward-compatible.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create companies and company_aliases tables and add company_id to job_listings."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            normalized_name VARCHAR(200) NOT NULL,
            slug VARCHAR(220) NOT NULL,
            logo_url TEXT,
            website_url TEXT,
            industry VARCHAR(100),
            headquarters VARCHAR(150) NOT NULL DEFAULT 'Phnom Penh',
            description TEXT,
            parent_company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            verification_status VARCHAR(20) NOT NULL DEFAULT 'unverified',
            verification_method VARCHAR(100),
            verified_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ix_companies_normalized_name ON companies(normalized_name);
        CREATE UNIQUE INDEX IF NOT EXISTS ix_companies_slug ON companies(slug);
        CREATE INDEX IF NOT EXISTS ix_companies_name ON companies(name);
        CREATE INDEX IF NOT EXISTS ix_companies_industry ON companies(industry);
        CREATE INDEX IF NOT EXISTS ix_companies_is_verified ON companies(is_verified);
        CREATE INDEX IF NOT EXISTS ix_companies_id ON companies(id);

        CREATE TABLE IF NOT EXISTS company_aliases (
            id SERIAL PRIMARY KEY,
            company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
            alias_name VARCHAR(200) NOT NULL,
            normalized_alias VARCHAR(200) NOT NULL,
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_company_aliases_company_alias UNIQUE (company_id, normalized_alias)
        );

        CREATE INDEX IF NOT EXISTS ix_company_aliases_company_id ON company_aliases(company_id);
        CREATE INDEX IF NOT EXISTS ix_company_aliases_source_id ON company_aliases(source_id);
        CREATE INDEX IF NOT EXISTS ix_company_aliases_normalized_alias ON company_aliases(normalized_alias);
        CREATE INDEX IF NOT EXISTS ix_company_aliases_id ON company_aliases(id);

        ALTER TABLE job_listings ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS ix_job_listings_company_id ON job_listings(company_id);
    """)


def downgrade() -> None:
    """Downgrade schema: drop company_id column, company_aliases table, and companies table."""
    op.execute("""
        DROP INDEX IF EXISTS ix_job_listings_company_id;
        ALTER TABLE job_listings DROP COLUMN IF EXISTS company_id;
        DROP TABLE IF EXISTS company_aliases CASCADE;
        DROP TABLE IF EXISTS companies CASCADE;
    """)

