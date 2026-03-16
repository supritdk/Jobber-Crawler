import random
from typing import AsyncIterator
import httpx
import structlog

from ..config import settings
from ..utils.rate_limiter import RateLimiter
from ..utils.retry import scrape_retry
from .base import BaseScraper, RawJobData, ScrapeRequest
from .registry import register_adapter

logger = structlog.get_logger()


@register_adapter("naukri")
class NaukriScraper(BaseScraper):
    """Scrapes jobs from Naukri.com using their public job search API.

    Naukri exposes a JSON API at:
        GET https://www.naukri.com/jobapi/v3/search
        Params: noOfResults, urlType, searchType, keyword, location, pageNo, ...

    The API returns paginated job listings with full details.
    """

    SEARCH_URL = "https://www.naukri.com/jobapi/v3/search"
    PAGE_SIZE = 20

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self):
        self._rate_limiter = RateLimiter(settings.naukri_rate_limit_rpm)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.naukri.com/",
                "systemId": "Jeeves",
                "appid": "109",
            },
        )

    @property
    def source_name(self) -> str:
        return "naukri"

    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        keywords_str = " ".join(request.keywords)
        page = 1
        total_yielded = 0

        while total_yielded < request.max_results:
            await self._rate_limiter.acquire()

            try:
                data = await self._fetch_page(keywords_str, request.location, page)
            except Exception:
                logger.exception("naukri_search_error", page=page)
                break

            job_details = data.get("jobDetails", [])
            if not job_details:
                logger.info("naukri_no_more_results", page=page)
                break

            for job in job_details:
                if total_yielded >= request.max_results:
                    break

                job_id = job.get("jobId")
                if not job_id:
                    continue

                yield RawJobData(
                    source="naukri",
                    external_id=str(job_id),
                    raw_data=job,
                )
                total_yielded += 1

            # Check if more pages
            no_of_jobs = data.get("noOfJobs", 0)
            if page * self.PAGE_SIZE >= no_of_jobs:
                break
            page += 1

    @scrape_retry
    async def _fetch_page(self, keywords: str, location: str | None, page: int) -> dict:
        # Naukri uses a URL-encoded keyword format
        keyword_slug = keywords.replace(" ", "-").lower()

        params = {
            "noOfResults": self.PAGE_SIZE,
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": keywords,
            "pageNo": page,
            "k": keywords,
            "seoKey": f"{keyword_slug}-jobs",
            "src": "jobsearchDesk",
            "latLong": "",
        }
        if location:
            params["location"] = location
            params["l"] = location

        headers = {"User-Agent": random.choice(self.USER_AGENTS)}
        response = await self._client.get(self.SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        try:
            headers = {"User-Agent": random.choice(self.USER_AGENTS)}
            response = await self._client.get(
                self.SEARCH_URL,
                params={"noOfResults": 1, "keyword": "test", "pageNo": 1},
                headers=headers,
            )
            return response.status_code == 200
        except Exception:
            return False
