from datetime import datetime

import structlog

from ..adapters.base import RawJobData
from ..adapters.registry import register_mapper
from ..schemas.job import ScrapedJobCreate
from .base import BaseFieldMapper

logger = structlog.get_logger()


@register_mapper("greenhouse")
class GreenhouseMapper(BaseFieldMapper):
    """Maps Greenhouse Job Board API response to ScrapedJobCreate.

    Greenhouse job object structure:
    {
        "id": 12345,
        "title": "Software Engineer",
        "updated_at": "2024-01-15T...",
        "location": {"name": "San Francisco, CA"},
        "content": "<p>Job description HTML...</p>",
        "departments": [{"name": "Engineering"}],
        "offices": [{"name": "SF Office"}],
        "absolute_url": "https://boards.greenhouse.io/company/jobs/12345",
        "metadata": [...],
        "company": {"name": "Acme Corp"}  # Only in board-level response
    }
    """

    def map(self, raw: RawJobData) -> ScrapedJobCreate:
        data = raw.raw_data

        # Parse location from nested object
        location = self.safe_get(data, "location", "name")

        # Extract plain text from HTML content
        description_html = data.get("content", "")
        description_text = self._strip_html(description_html)

        # Parse departments as job function
        departments = data.get("departments", [])
        job_function = ", ".join(d.get("name", "") for d in departments if d.get("name"))

        # Parse posted date
        posted_at = None
        updated_str = data.get("updated_at")
        if updated_str:
            try:
                posted_at = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return ScrapedJobCreate(
            external_id=raw.external_id,
            title=data.get("title"),
            company_name=data.get("company_name") or self.safe_get(data, "company", "name"),
            description_text=description_text,
            apply_url=data.get("absolute_url"),
            source_url=data.get("absolute_url"),
            source="greenhouse",
            location=location,
            employment_type=self._extract_metadata(data, "employment_type"),
            seniority_level=self._extract_metadata(data, "seniority_level"),
            is_easy_apply=False,
            job_function=job_function or None,
            posted_at=posted_at,
        )

    @staticmethod
    def _strip_html(html: str) -> str:
        """Remove HTML tags to get plain text."""
        if not html:
            return ""
        import html as html_module
        from html.parser import HTMLParser
        from io import StringIO

        # Unescape HTML entities first (&lt; -> <, &amp; -> &, etc.)
        unescaped = html_module.unescape(html)

        class HTMLStripper(HTMLParser):
            def __init__(self):
                super().__init__()
                self.result = StringIO()

            def handle_data(self, data):
                self.result.write(data + " ")

        stripper = HTMLStripper()
        stripper.feed(unescaped)
        # Clean up extra whitespace
        text = stripper.result.getvalue()
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _extract_metadata(data: dict, key: str) -> str | None:
        """Extract a value from Greenhouse metadata array."""
        metadata = data.get("metadata", [])
        if not isinstance(metadata, list):
            return None
        for item in metadata:
            if isinstance(item, dict) and item.get("name") == key:
                return item.get("value")
        return None
