from datetime import datetime

import structlog

from ..adapters.base import RawJobData
from ..adapters.registry import register_mapper
from ..schemas.job import ScrapedJobCreate
from .base import BaseFieldMapper

logger = structlog.get_logger()


@register_mapper("naukri")
class NaukriMapper(BaseFieldMapper):
    """Maps Naukri API response to ScrapedJobCreate.

    Naukri jobDetails item structure:
    {
        "jobId": "123456",
        "title": "Software Engineer",
        "companyName": "Acme Corp",
        "jdURL": "https://www.naukri.com/job-listings-...",
        "jobDescription": "Full description...",
        "tagsAndSkills": "Python, Django, REST API",
        "placeholders": {
            "experience": "2-5 years",
            "salary": "8-15 Lacs PA",
            "location": "Bangalore"
        },
        "footerPlaceholderLabel": "Full Time",
        "companyId": "789",
        "logoPath": "https://img.naukri.com/...",
        "logoPathV3": "https://img.naukri.com/...",
        "createdDate": "2024-01-15T00:00:00Z",
        "ambitionBoxData": {
            "companyUrl": "https://www.ambitionbox.com/...",
            "Rating": "3.5",
            "Reviews": "500"
        },
        "staticUrl": "https://www.naukri.com/job-listings-...",
        "isSaved": false,
        "boardProviderName": "naukri",
        "industryTypeGids": [...],
        "functionalAreaGids": [...]
    }
    """

    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        data = raw.raw_data
        placeholders = data.get("placeholders", {})

        # Parse posted date
        posted_at = None
        created = data.get("createdDate")
        if created:
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Location from placeholders
        location_items = placeholders.get("location", "")
        if isinstance(location_items, list):
            location = ", ".join(location_items)
        else:
            location = str(location_items) if location_items else None

        # Salary from placeholders
        salary = placeholders.get("salary")
        if isinstance(salary, list):
            salary = ", ".join(salary)

        return ScrapedJobCreate(
            external_id=raw.external_id,
            title=data.get("title"),
            company_name=data.get("companyName"),
            description_text=data.get("jobDescription"),
            apply_url=data.get("jdURL"),
            source_url=data.get("jdURL") or data.get("staticUrl"),
            source="naukri",
            location=location,
            salary=str(salary) if salary else None,
            employment_type=data.get("footerPlaceholderLabel"),
            seniority_level=self._infer_seniority(data.get("title", "")),
            is_easy_apply=False,
            company_logo=data.get("logoPathV3") or data.get("logoPath"),
            industries=data.get("tagsAndSkills"),
            posted_at=posted_at,
        )

    @staticmethod
    def _infer_seniority(title: str) -> str | None:
        """Infer seniority level from job title."""
        title_lower = title.lower()
        if any(k in title_lower for k in ["senior", "sr.", "sr ", "lead"]):
            return "Senior"
        if any(k in title_lower for k in ["junior", "jr.", "jr ", "entry", "fresher", "trainee"]):
            return "Entry"
        if any(k in title_lower for k in ["director", "head of", "vp", "vice president"]):
            return "Director"
        if any(k in title_lower for k in ["manager", "principal", "staff"]):
            return "Mid-Senior"
        return None
