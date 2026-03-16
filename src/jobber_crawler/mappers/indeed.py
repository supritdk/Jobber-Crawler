import structlog

from ..adapters.base import RawJobData
from ..adapters.registry import register_mapper
from ..schemas.job import ScrapedJobCreate
from .base import BaseFieldMapper

logger = structlog.get_logger()


@register_mapper("indeed")
class IndeedMapper(BaseFieldMapper):
    """Maps Indeed scraped data to ScrapedJobCreate.

    Raw data from IndeedScraper:
    {
        "job_id": "abc123def",
        "title": "Software Engineer",
        "company_name": "Acme Corp",
        "location": "San Francisco, CA",
        "salary": "$120,000 - $160,000 a year",
        "description_snippet": "We are looking for...",
        "posted_text": "Posted 3 days ago",
        "source_url": "https://www.indeed.com/viewjob?jk=abc123def",
    }
    """

    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        data = raw.raw_data

        return ScrapedJobCreate(
            external_id=raw.external_id,
            title=data.get("title"),
            company_name=data.get("company_name"),
            description_text=data.get("description_snippet"),
            apply_url=data.get("source_url"),  # Indeed redirects to company portal
            source_url=data.get("source_url"),
            source="indeed",
            location=data.get("location"),
            salary=data.get("salary"),
            is_easy_apply=False,
            employment_type=data.get("employment_type"),
        )
