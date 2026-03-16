"""Create scraped_jobs table

Revision ID: 001
Revises:
Create Date: 2026-03-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scraped_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("company_name", sa.String(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("apply_url", sa.String(), nullable=True),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("salary", sa.String(), nullable=True),
        sa.Column("salary_info", postgresql.JSONB(), nullable=True),
        sa.Column("employment_type", sa.String(), nullable=True),
        sa.Column("seniority_level", sa.String(), nullable=True),
        sa.Column("is_easy_apply", sa.Boolean(), default=False),
        sa.Column("company_website", sa.String(), nullable=True),
        sa.Column("company_logo", sa.String(), nullable=True),
        sa.Column("industries", sa.String(), nullable=True),
        sa.Column("job_function", sa.String(), nullable=True),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applicants_count", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    op.create_index(
        "ix_scraped_jobs_dedup",
        "scraped_jobs",
        ["external_id", "source"],
        unique=True,
    )
    op.create_index("ix_scraped_jobs_source", "scraped_jobs", ["source"])
    op.create_index("ix_scraped_jobs_posted_at", "scraped_jobs", ["posted_at"])
    op.create_index("ix_scraped_jobs_company", "scraped_jobs", ["company_name"])


def downgrade() -> None:
    op.drop_index("ix_scraped_jobs_company", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_posted_at", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_source", table_name="scraped_jobs")
    op.drop_index("ix_scraped_jobs_dedup", table_name="scraped_jobs")
    op.drop_table("scraped_jobs")
