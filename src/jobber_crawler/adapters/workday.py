from typing import AsyncIterator

import httpx
import structlog

from ..config import settings
from ..utils.rate_limiter import RateLimiter
from ..utils.retry import scrape_retry
from .base import BaseScraper, RawJobData, ScrapeRequest
from .registry import register_adapter

logger = structlog.get_logger()


@register_adapter("workday")
class WorkdayScraper(BaseScraper):
    """Scrapes jobs from Workday career sites.

    Each company has a Workday tenant URL like:
        https://company.wd5.myworkdayjobs.com

    The search API endpoint is:
        POST /wday/cxs/{tenant}/jobs
        Body: {"searchText": "...", "limit": 20, "offset": 0, ...}

    Configure tenant URLs via JOBBER_WORKDAY_TENANT_URLS env var (comma-separated).
    """

    PAGE_SIZE = 20

    def __init__(self):
        self._rate_limiter = RateLimiter(settings.workday_rate_limit_rpm)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    @property
    def source_name(self) -> str:
        return "workday"

    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        tenant_urls = settings.get_workday_urls()
        if not tenant_urls:
            logger.warning("no_workday_tenant_urls_configured")
            return

        keywords_str = " ".join(request.keywords)
        total_yielded = 0

        for base_url in tenant_urls:
            if total_yielded >= request.max_results:
                break

            # Extract tenant name from URL for API path
            tenant = self._extract_tenant(base_url)
            if not tenant:
                logger.warning("invalid_workday_url", url=base_url)
                continue

            try:
                async for job in self._scrape_tenant(
                    base_url, tenant, keywords_str, request.max_results - total_yielded
                ):
                    yield job
                    total_yielded += 1
            except Exception:
                logger.exception("workday_tenant_error", tenant=tenant)
                continue

    async def _scrape_tenant(
        self, base_url: str, tenant: str, keywords: str, max_results: int
    ) -> AsyncIterator[RawJobData]:
        offset = 0
        count = 0

        while count < max_results:
            await self._rate_limiter.acquire()
            try:
                data = await self._fetch_page(base_url, tenant, keywords, offset)
            except Exception:
                logger.exception("workday_page_error", tenant=tenant, offset=offset)
                break

            job_postings = data.get("jobPostings", [])
            if not job_postings:
                break

            for posting in job_postings:
                if count >= max_results:
                    break

                external_id = posting.get("bulletFields", [None])[0] or str(
                    posting.get("id", "")
                )

                # Fetch full job detail
                detail_path = posting.get("externalPath", "")
                if detail_path:
                    await self._rate_limiter.acquire()
                    try:
                        detail = await self._fetch_detail(base_url, tenant, detail_path)
                        posting["detail"] = detail
                    except Exception:
                        logger.exception("workday_detail_error", path=detail_path)

                posting["tenant_url"] = base_url
                posting["tenant"] = tenant

                yield RawJobData(
                    source="workday",
                    external_id=external_id,
                    raw_data=posting,
                )
                count += 1

            total = data.get("total", 0)
            offset += self.PAGE_SIZE
            if offset >= total:
                break

    @scrape_retry
    async def _fetch_page(
        self, base_url: str, tenant: str, keywords: str, offset: int
    ) -> dict:
        url = f"{base_url.rstrip('/')}/wday/cxs/{tenant}/jobs"
        body = {
            "appliedFacets": {},
            "limit": self.PAGE_SIZE,
            "offset": offset,
            "searchText": keywords,
        }
        response = await self._client.post(url, json=body)
        response.raise_for_status()
        return response.json()

    @scrape_retry
    async def _fetch_detail(self, base_url: str, tenant: str, path: str) -> dict:
        url = f"{base_url.rstrip('/')}/wday/cxs/{tenant}{path}"
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _extract_tenant(url: str) -> str | None:
        """Extract tenant name from Workday URL.
        e.g. https://company.wd5.myworkdayjobs.com -> company
        """
        import re

        match = re.search(r"https?://([^.]+)\.wd\d+\.myworkdayjobs\.com", url)
        return match.group(1) if match else None

    async def health_check(self) -> bool:
        urls = settings.get_workday_urls()
        if not urls:
            return False
        try:
            response = await self._client.get(urls[0])
            return response.status_code < 500
        except Exception:
            return False
