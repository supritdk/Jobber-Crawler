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
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


@register_adapter("linkedin")
class LinkedInScraper(BaseScraper):
    """Scrapes LinkedIn jobs using the guest (unauthenticated) job search API.

    Endpoints:
    - List: /jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=...&location=...&start=N
    - Detail: /jobs-guest/jobs/api/jobPosting/{job_id}

    Returns HTML fragments that are parsed with BeautifulSoup.
    """

    BASE_URL = "https://www.linkedin.com"
    SEARCH_URL = f"{BASE_URL}/jobs-guest/jobs/api/seeMoreJobPostings/search"
    DETAIL_URL = f"{BASE_URL}/jobs-guest/jobs/api/jobPosting"
    PAGE_SIZE = 25

    def __init__(self):
        self._rate_limiter = RateLimiter(settings.linkedin_rate_limit_rpm)
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )

    @property
    def source_name(self) -> str:
        return "linkedin"

    async def scrape(self, request: ScrapeRequest) -> AsyncIterator[RawJobData]:
        keywords_str = " ".join(request.keywords)
        start = 0
        total_yielded = 0

        while total_yielded < request.max_results:
            await self._rate_limiter.acquire()

            try:
                job_cards = await self._fetch_search_page(
                    keywords_str, request.location, start, request.posted_within_hours
                )
            except Exception:
                logger.exception("linkedin_search_error", start=start)
                break

            if not job_cards:
                logger.info("linkedin_no_more_results", start=start)
                break

            for card in job_cards:
                if total_yielded >= request.max_results:
                    break

                job_id = self._extract_job_id(card)
                if not job_id:
                    continue

                # Fetch job detail page
                await self._rate_limiter.acquire()
                try:
                    detail = await self._fetch_job_detail(job_id)
                    raw_data = self._parse_job_card(card)
                    raw_data.update(self._parse_job_detail(detail))
                    raw_data["job_id"] = job_id

                    yield RawJobData(
                        source="linkedin",
                        external_id=job_id,
                        raw_data=raw_data,
                    )
                    total_yielded += 1
                except Exception:
                    logger.exception("linkedin_detail_error", job_id=job_id)
                    continue

            start += self.PAGE_SIZE

    @scrape_retry
    async def _fetch_search_page(
        self, keywords: str, location: str | None, start: int, posted_within_hours: int | None = None
    ) -> list:
        params = {
            "keywords": keywords,
            "start": start,
            "sortBy": "DD",  # Date descending
        }
        if location:
            params["location"] = location
        if posted_within_hours:
            params["f_TPR"] = f"r{posted_within_hours * 3600}"

        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = await self._client.get(self.SEARCH_URL, params=params, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")
        return soup.find_all("li")

    @scrape_retry
    async def _fetch_job_detail(self, job_id: str) -> BeautifulSoup:
        url = f"{self.DETAIL_URL}/{job_id}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = await self._client.get(url, headers=headers)
        response.raise_for_status()
        return BeautifulSoup(response.text, "lxml")

    @staticmethod
    def _extract_job_id(card) -> str | None:
        """Extract job ID from a search result card."""
        # Try data-entity-urn on the card itself or nested div
        urn = card.get("data-entity-urn", "")
        if not urn:
            div = card.find("div", attrs={"data-entity-urn": True})
            if div:
                urn = div.get("data-entity-urn", "")
        if urn:
            match = re.search(r"(\d+)$", urn)
            if match:
                return match.group(1)

        # Try link href
        link = card.find("a", href=True)
        if link:
            match = re.search(r"/jobs/view/(\d+)", link["href"])
            if match:
                return match.group(1)

        return None

    @staticmethod
    def _parse_job_card(card) -> dict:
        """Parse basic info from a search result card."""
        data = {}

        title_el = card.find("h3", class_=re.compile("base-search-card__title"))
        if title_el:
            data["title"] = title_el.get_text(strip=True)

        company_el = card.find("h4", class_=re.compile("base-search-card__subtitle"))
        if company_el:
            data["company_name"] = company_el.get_text(strip=True)

        location_el = card.find("span", class_=re.compile("job-search-card__location"))
        if location_el:
            data["location"] = location_el.get_text(strip=True)

        time_el = card.find("time")
        if time_el:
            data["posted_at"] = time_el.get("datetime", "")

        link_el = card.find("a", class_=re.compile("base-card__full-link"))
        if link_el:
            data["source_url"] = link_el.get("href", "").split("?")[0]

        logo_el = card.find("img", class_=re.compile("artdeco-entity-image"))
        if logo_el:
            data["company_logo"] = logo_el.get("data-delayed-url") or logo_el.get("src")

        return data

    @staticmethod
    def _parse_job_detail(soup: BeautifulSoup) -> dict:
        """Parse detailed info from a job detail page."""
        data = {}

        # Description
        desc_el = soup.find("div", class_=re.compile("description"))
        if desc_el:
            data["description_text"] = desc_el.get_text(separator="\n", strip=True)

        # Criteria list (seniority, employment type, function, industries)
        criteria_items = soup.find_all("li", class_=re.compile("description__job-criteria-item"))
        for item in criteria_items:
            header = item.find("h3")
            value = item.find("span", class_=re.compile("description__job-criteria-text"))
            if header and value:
                header_text = header.get_text(strip=True).lower()
                value_text = value.get_text(strip=True)
                if "seniority" in header_text:
                    data["seniority_level"] = value_text
                elif "employment" in header_text:
                    data["employment_type"] = value_text
                elif "function" in header_text:
                    data["job_function"] = value_text
                elif "industr" in header_text:
                    data["industries"] = value_text

        # Apply URL
        apply_el = soup.find("a", class_=re.compile("apply-button"))
        if apply_el:
            href = apply_el.get("href", "")
            if href and "linkedin.com" not in href:
                data["apply_url"] = href
                data["is_easy_apply"] = False
            else:
                data["is_easy_apply"] = True

        # Applicants count
        applicants_el = soup.find("span", class_=re.compile("num-applicants__caption"))
        if applicants_el:
            data["applicants_count"] = applicants_el.get_text(strip=True)

        # Salary
        salary_el = soup.find("div", class_=re.compile("salary"))
        if salary_el:
            data["salary"] = salary_el.get_text(strip=True)

        return data

    async def health_check(self) -> bool:
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = await self._client.get(
                self.SEARCH_URL,
                params={"keywords": "test", "start": 0},
                headers=headers,
            )
            return response.status_code == 200
        except Exception:
            return False
