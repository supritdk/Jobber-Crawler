from datetime import datetime

import structlog

from ..adapters.base import RawJobData
from ..adapters.registry import register_mapper
from ..schemas.job import ScrapedJobCreate
from .base import BaseFieldMapper

logger = structlog.get_logger()


@register_mapper("workday")
class WorkdayMapper(BaseFieldMapper):
    """Maps Workday career site API response to ScrapedJobCreate.

    Workday job posting structure:
    {
        "title": "Software Engineer",
        "locationsText": "San Francisco, CA",
        "postedOn": "Posted 3 Days Ago",
        "bulletFields": ["REQ-12345"],
        "externalPath": "/job/Software-Engineer/REQ-12345",
        "tenant_url": "https://company.wd5.myworkdayjobs.com",
        "tenant": "company",
        "detail": {
            "jobPostingInfo": {
                "jobDescription": "Full description...",
                "externalUrl": "https://...",
                "startDate": "2024-01-15",
                "jobReqId": "REQ-12345",
                "company": "Acme Corp",
                ...
            }
        }
    }
    """

    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        data = raw.raw_data
        detail = data.get("detail", {})
        job_info = detail.get("jobPostingInfo", {})

        # Build source URL from tenant URL + external path
        tenant_url = data.get("tenant_url", "")
        external_path = data.get("externalPath", "")
        source_url = f"{tenant_url.rstrip('/')}{external_path}" if external_path else None

        # Parse posted date
        posted_at = None
        start_date = job_info.get("startDate")
        if start_date:
            try:
                posted_at = datetime.fromisoformat(start_date)
            except (ValueError, TypeError):
                pass

        # Extract apply URL
        apply_url = job_info.get("externalUrl") or source_url

        return ScrapedJobCreate(
            external_id=raw.external_id,
            title=data.get("title"),
            company_name=job_info.get("company") or data.get("tenant"),
            description_text=job_info.get("jobDescription"),
            apply_url=apply_url,
            source_url=source_url,
            source="workday",
            location=data.get("locationsText"),
            employment_type=job_info.get("timeType"),
            is_easy_apply=False,
            posted_at=posted_at,
        )
