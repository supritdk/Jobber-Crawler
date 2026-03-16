from datetime import datetime

import structlog

from ..adapters.base import RawJobData
from ..adapters.registry import register_mapper
from ..schemas.job import ScrapedJobCreate
from .base import BaseFieldMapper

logger = structlog.get_logger()


@register_mapper("linkedin")
class LinkedInMapper(BaseFieldMapper):
    """Maps LinkedIn guest API scraped data to ScrapedJobCreate.

    The raw_data comes from LinkedInScraper which combines card + detail data:
    {
        "job_id": "12345",
        "title": "Software Engineer",
        "company_name": "Acme Corp",
        "location": "San Francisco, CA",
        "posted_at": "2024-01-15",
        "source_url": "https://www.linkedin.com/jobs/view/12345",
        "company_logo": "https://...",
        "description_text": "Full job description...",
        "seniority_level": "Mid-Senior level",
        "employment_type": "Full-time",
        "job_function": "Engineering",
        "industries": "Technology",
        "apply_url": "https://company.com/apply",
        "is_easy_apply": True,
        "applicants_count": "200 applicants",
        "salary": "$120,000 - $160,000",
    }
    """

    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        data = raw.raw_data

        posted_at = None
        posted_str = data.get("posted_at")
        if posted_str:
            try:
                posted_at = datetime.fromisoformat(posted_str)
            except (ValueError, TypeError):
                pass

        return ScrapedJobCreate(
            external_id=raw.external_id,
            title=data.get("title"),
            company_name=data.get("company_name"),
            description_text=data.get("description_text"),
            apply_url=data.get("apply_url"),
            source_url=data.get("source_url"),
            source="linkedin",
            location=data.get("location"),
            salary=data.get("salary"),
            employment_type=data.get("employment_type"),
            seniority_level=data.get("seniority_level"),
            is_easy_apply=data.get("is_easy_apply", False),
            company_logo=data.get("company_logo"),
            industries=data.get("industries"),
            job_function=data.get("job_function"),
            posted_at=posted_at,
            applicants_count=data.get("applicants_count"),
        )
