import random
import re
from typing import AsyncIterator

import httpx
import structlog
from bs4 import BeautifulSoup

from ..config import settings
from ..utils.rate_limiter import RateLimiter
from ..utils.retry import scrape_retry
from .base import BaseScraper, RawJobData, ScrapeRequest
from .registry import register_adapter

logger = structlog.get_logger()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


@register_adapter("indeed")
class IndeedScraper(BaseScraper):
    """Scrapes jobs from Indeed.

    Uses Indeed's public search pages. Indeed has aggressive bot detection,
    so this adapter uses careful rate limiting and user-agent rotation.

    For production use, consider using the Indeed Publisher API if you have
    a publisher ID (set JOBBER_INDEED_PUBLISHER_ID in .env).
    """

    SEARCH_URL = "https://www.indeed.com/jobs"
    PAGE_SIZE = 15  # Indeed shows ~15 results per page

    def __init__(self):
        self._rate_limiter = RateLimiter(settings.indeed_rate_limit_rpm)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    @property
    def source_name(self) -> str:
        return "indeed"

    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        keywords_str = " ".join(request.keywords)
        start = 0
        total_yielded = 0

        while total_yielded < request.max_results:
            await self._rate_limiter.acquire()

            try:
                job_cards = await self._fetch_search_page(
                    keywords_str, request.location, start
                )
            except Exception:
                logger.exception("indeed_search_error", start=start)
                break

            if not job_cards:
                logger.info("indeed_no_more_results", start=start)
                break

            for card_data in job_cards:
                if total_yielded >= request.max_results:
                    break

                job_id = card_data.get("job_id")
                if not job_id:
                    continue

                yield RawJobData(
                    source="indeed",
                    external_id=job_id,
                    raw_data=card_data,
                )
                total_yielded += 1

            start += self.PAGE_SIZE

    @scrape_retry
    async def _fetch_search_page(
        self, keywords: str, location: str | None, start: int
    ) -> list[dict]:
        params = {
            "q": keywords,
            "start": start,
            "sort": "date",
        }
        if location:
            params["l"] = location

        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = await self._client.get(self.SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()

        return self._parse_search_results(response.text)

    @staticmethod
    def _parse_search_results(html: str) -> list[dict]:
        """Parse job cards from Indeed search results page."""
        soup = BeautifulSoup(html, "lxml")
        results = []

        job_cards = soup.find_all("div", class_=re.compile("job_seen_beacon|jobsearch-ResultsList"))
        if not job_cards:
            # Fallback: try finding by data attributes
            job_cards = soup.find_all("a", attrs={"data-jk": True})

        for card in job_cards:
            data = {}

            # Job ID from data-jk attribute
            jk = card.get("data-jk") or ""
            if not jk:
                link = card.find("a", attrs={"data-jk": True})
                if link:
                    jk = link.get("data-jk", "")
            if not jk:
                # Try to extract from href
                link = card.find("a", href=re.compile(r"jk="))
                if link:
                    match = re.search(r"jk=([a-f0-9]+)", link.get("href", ""))
                    if match:
                        jk = match.group(1)

            if not jk:
                continue

            data["job_id"] = jk

            # Title
            title_el = card.find("h2", class_=re.compile("jobTitle"))
            if title_el:
                # Get the span inside
                span = title_el.find("span")
                data["title"] = (span or title_el).get_text(strip=True)

            # Company
            company_el = card.find("span", attrs={"data-testid": "company-name"})
            if not company_el:
                company_el = card.find("span", class_=re.compile("companyName|company"))
            if company_el:
                data["company_name"] = company_el.get_text(strip=True)

            # Location
            location_el = card.find("div", attrs={"data-testid": "text-location"})
            if not location_el:
                location_el = card.find("div", class_=re.compile("companyLocation"))
            if location_el:
                data["location"] = location_el.get_text(strip=True)

            # Salary
            salary_el = card.find("div", class_=re.compile("salary-snippet|estimated-salary"))
            if salary_el:
                data["salary"] = salary_el.get_text(strip=True)

            # Snippet / description
            snippet_el = card.find("div", class_=re.compile("job-snippet"))
            if snippet_el:
                data["description_snippet"] = snippet_el.get_text(strip=True)

            # Posted date
            date_el = card.find("span", class_=re.compile("date"))
            if date_el:
                data["posted_text"] = date_el.get_text(strip=True)

            # Source URL
            data["source_url"] = f"https://www.indeed.com/viewjob?jk={jk}"

            results.append(data)

        return results

    async def health_check(self) -> bool:
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = await self._client.get(
                self.SEARCH_URL,
                params={"q": "test", "start": 0},
                headers=headers,
            )
            return response.status_code == 200
        except Exception:
            return False
