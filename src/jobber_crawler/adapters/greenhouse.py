from typing import AsyncIterator

import httpx
import structlog

from ..config import settings
from ..utils.rate_limiter import RateLimiter
from ..utils.retry import scrape_retry
from .base import BaseScraper, RawJobData, ScrapeRequest
from .registry import register_adapter

logger = structlog.get_logger()


@register_adapter("greenhouse")
class GreenhouseScraper(BaseScraper):
    """Scrapes jobs from Greenhouse public Job Board API.

    API docs: https://developers.greenhouse.io/job-board.html
    Endpoint: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs
    """

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self):
        self._rate_limiter = RateLimiter(settings.greenhouse_rate_limit_rpm)
        self._client = httpx.AsyncClient(timeout=30.0)

    @property
    def source_name(self) -> str:
        return "greenhouse"

    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        board_tokens = settings.get_greenhouse_tokens()
        if not board_tokens:
            logger.warning("no_greenhouse_tokens_configured")
            return

        for token in board_tokens:
            try:
                async for job in self._scrape_board(token, request):
                    yield job
            except Exception:
                logger.exception("greenhouse_board_error", board_token=token)
                continue

    async def _scrape_board(
        self, board_token: str, request: ScrapeRequest
    ) -> AsyncIterator[RawJobData]:
        await self._rate_limiter.acquire()
        jobs_data = await self._fetch_jobs_list(board_token)

        count = 0
        for job in jobs_data:
            if count >= request.max_results:
                break

            # Fetch full job details (includes description)
            await self._rate_limiter.acquire()
            try:
                job_detail = await self._fetch_job_detail(board_token, job["id"])
                yield RawJobData(
                    source="greenhouse",
                    external_id=str(job["id"]),
                    raw_data=job_detail,
                )
                count += 1
            except Exception:
                logger.exception("greenhouse_job_detail_error", job_id=job["id"])
                continue

    @scrape_retry
    async def _fetch_jobs_list(self, board_token: str) -> list[dict]:
        url = f"{self.BASE_URL}/{board_token}/jobs"
        response = await self._client.get(url, params={"content": "true"})
        response.raise_for_status()
        data = response.json()
        return data.get("jobs", [])

    @scrape_retry
    async def _fetch_job_detail(self, board_token: str, job_id: int) -> dict:
        url = f"{self.BASE_URL}/{board_token}/jobs/{job_id}"
        response = await self._client.get(url, params={"questions": "true"})
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        try:
            tokens = settings.get_greenhouse_tokens()
            if not tokens:
                return False
            response = await self._client.get(f"{self.BASE_URL}/{tokens[0]}/jobs")
            return response.status_code == 200
        except Exception:
            return False
