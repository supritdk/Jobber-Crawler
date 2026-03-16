from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ScrapedJobCreate(BaseModel):
    external_id: str
    title: str | None = None
    company_name: str | None = None
    description_text: str | None = None
    apply_url: str | None = None
    source_url: str | None = None
    source: str
    location: str | None = None
    salary: str | None = None
    salary_info: dict | None = None
    employment_type: str | None = None
    seniority_level: str | None = None
    is_easy_apply: bool = False
    company_website: str | None = None
    company_logo: str | None = None
    industries: str | None = None
    job_function: str | None = None
    benefits: str | None = None
    posted_at: datetime | None = None
    applicants_count: str | None = None
    category: str | None = None


class ScrapedJobResponse(ScrapedJobCreate):
    id: UUID
    deleted_at: datetime | None = None
    synced_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
