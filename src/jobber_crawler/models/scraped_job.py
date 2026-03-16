import uuid

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..database import Base


class ScrapedJob(Base):
    __tablename__ = "scraped_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    company_name: Mapped[str | None] = mapped_column(String, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    salary: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    seniority_level: Mapped[str | None] = mapped_column(String, nullable=True)
    is_easy_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    company_website: Mapped[str | None] = mapped_column(String, nullable=True)
    company_logo: Mapped[str | None] = mapped_column(String, nullable=True)
    industries: Mapped[str | None] = mapped_column(String, nullable=True)
    job_function: Mapped[str | None] = mapped_column(String, nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applicants_count: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    deleted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_scraped_jobs_dedup", "external_id", "source", unique=True),
        Index("ix_scraped_jobs_source", "source"),
        Index("ix_scraped_jobs_posted_at", "posted_at"),
        Index("ix_scraped_jobs_company", "company_name"),
    )

    def __repr__(self) -> str:
        return f"<ScrapedJob {self.source}:{self.external_id} - {self.title}>"
